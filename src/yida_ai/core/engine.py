from __future__ import annotations

import logging
import queue
import threading
from dataclasses import dataclass

from yida_ai.core.conversation import ConversationManager
from yida_ai.core.models import CaptionEvent, ReplyRequest, ReplySuggestion
from yida_ai.providers.llm.base import LLMProvider
from yida_ai.retrieval.base import KnowledgeRetriever
from yida_ai.storage.history import HistoryStore, StorageError

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class _Job:
    sequence: int
    generation: int
    request: ReplyRequest


@dataclass(frozen=True, slots=True)
class EngineResult:
    sequence: int
    generation: int
    request: ReplyRequest
    suggestion: ReplySuggestion | None = None
    error: str = ""
    warning: str = ""


class ReplyEngine:
    def __init__(
        self,
        provider: LLMProvider,
        retriever: KnowledgeRetriever,
        conversation: ConversationManager,
        history: HistoryStore | None = None,
        *,
        scene: str = "general",
        custom_scene_instruction: str = "",
        user_language: str = "zh-CN",
        reply_language: str = "pt-BR",
        reply_length: str = "short",
        workers: int = 2,
        max_queue: int = 4,
    ) -> None:
        self.provider = provider
        self.retriever = retriever
        self.conversation = conversation
        self.history = history
        self.scene = scene
        self.custom_scene_instruction = custom_scene_instruction
        self.user_language = user_language
        self.reply_language = reply_language
        self.reply_length = reply_length
        self._jobs: queue.Queue[_Job | None] = queue.Queue(maxsize=max_queue)
        self._results: queue.Queue[EngineResult] = queue.Queue()
        self._threads: list[threading.Thread] = []
        self._closed = False
        self._sequence = 0
        self._next_delivery = 1
        self._completed: dict[int, EngineResult] = {}
        self._skipped: set[int] = set()
        self._lock = threading.Lock()
        for index in range(max(1, workers)):
            thread = threading.Thread(
                target=self._worker,
                name=f"yida-reply-{index + 1}",
                daemon=True,
            )
            thread.start()
            self._threads.append(thread)

    @property
    def queue_size(self) -> int:
        return self._jobs.qsize()

    def submit(self, event: CaptionEvent, *, record_event: bool = True) -> str:
        if self._closed:
            raise RuntimeError("回复引擎已关闭")
        if record_event:
            self.conversation.add_event(event)
        citations = self.retriever.retrieve(
            f"{event.source_text}\n{event.translated_text}", limit=3
        )
        context = self.conversation.events[-self.conversation.context_turns :]
        request = ReplyRequest(
            event=event,
            context=context,
            citations=citations,
            scene=self.scene,
            user_language=self.user_language,
            reply_language=self.reply_language,
            reply_length=self.reply_length,
            session_id=self.conversation.session_id,
            scene_instruction=(self.custom_scene_instruction if self.scene == "custom" else ""),
        )
        with self._lock:
            self._sequence += 1
            job = _Job(self._sequence, self.conversation.generation, request)
            try:
                self._jobs.put_nowait(job)
            except queue.Full:
                try:
                    discarded = self._jobs.get_nowait()
                    if discarded is not None:
                        self._skipped.add(discarded.sequence)
                    self._jobs.task_done()
                except queue.Empty:
                    pass
                self._jobs.put_nowait(job)
        return request.request_id

    def drain_results(self) -> list[EngineResult]:
        while True:
            try:
                result = self._results.get_nowait()
            except queue.Empty:
                break
            self._completed[result.sequence] = result
        delivered: list[EngineResult] = []
        while True:
            if self._next_delivery in self._skipped:
                self._skipped.remove(self._next_delivery)
                self._next_delivery += 1
                continue
            result = self._completed.pop(self._next_delivery, None)
            if result is None:
                break
            self._next_delivery += 1
            if (
                result.generation != self.conversation.generation
                or result.request.session_id != self.conversation.session_id
            ):
                continue
            if result.suggestion is not None:
                self.conversation.attach_suggestion(
                    result.request.event.event_id, result.suggestion
                )
                if self.history is not None:
                    try:
                        self.history.save(
                            self.conversation.session_id,
                            result.request.event,
                            result.suggestion,
                        )
                    except StorageError as exc:
                        LOGGER.warning(
                            "History save failed for request %s", result.request.request_id
                        )
                        result = EngineResult(
                            result.sequence,
                            result.generation,
                            result.request,
                            result.suggestion,
                            warning=str(exc),
                        )
            delivered.append(result)
        return delivered

    def clear_session(self) -> None:
        self.conversation.clear()
        with self._lock:
            self._completed.clear()
            self._skipped.update(range(self._next_delivery, self._sequence + 1))

    def shutdown(self, timeout: float = 2.0) -> None:
        if self._closed:
            return
        self._closed = True
        for _ in self._threads:
            try:
                self._jobs.put_nowait(None)
            except queue.Full:
                break
        for thread in self._threads:
            thread.join(timeout=timeout)

    def _worker(self) -> None:
        while not self._closed:
            try:
                job = self._jobs.get(timeout=0.2)
            except queue.Empty:
                continue
            if job is None:
                self._jobs.task_done()
                return
            try:
                suggestion = self.provider.generate(job.request)
                result = EngineResult(job.sequence, job.generation, job.request, suggestion)
            except Exception as exc:
                LOGGER.warning(
                    "AI provider failed for request %s (%s)",
                    job.request.request_id,
                    type(exc).__name__,
                )
                result = EngineResult(
                    job.sequence,
                    job.generation,
                    job.request,
                    error=str(exc),
                )
            self._results.put(result)
            self._jobs.task_done()


def should_generate(mode: str, event: CaptionEvent) -> bool:
    if mode in {"translation", "confirm"}:
        return False
    if mode == "every":
        return True
    text = f"{event.source_text} {event.translated_text}".casefold()
    markers = (
        "?",
        "？",
        "please",
        "could",
        "would",
        "why",
        "how",
        "请",
        "吗",
        "如何",
        "为什么",
        "por favor",
        "como",
        "por quê",
    )
    return any(marker in text for marker in markers)
