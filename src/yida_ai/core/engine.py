from __future__ import annotations

import logging
import queue
import threading
from collections import OrderedDict
from dataclasses import dataclass

from yida_ai.core.conversation import ConversationManager
from yida_ai.core.models import CaptionEvent, ReplyRequest, ReplySuggestion
from yida_ai.providers.llm.base import LLMError, LLMErrorKind, LLMProvider
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
    error_kind: LLMErrorKind | None = None


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
        self._results: queue.Queue[EngineResult] = queue.Queue(
            maxsize=max(32, max_queue * max(1, workers) * 8)
        )
        self._threads: list[threading.Thread] = []
        self._closed = False
        self._sequence = 0
        self._next_delivery = 1
        self._completed: dict[int, EngineResult] = {}
        self._skipped: set[int] = set()
        self._lock = threading.Lock()
        self._latest_requests: OrderedDict[str, str | None] = OrderedDict()
        self._event_sequences: dict[str, int] = {}
        self._queue_drops = 0
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

    @property
    def queue_drops(self) -> int:
        return self._queue_drops

    def backlog_status(self) -> str:
        if self._queue_drops:
            return f"AI 回复队列繁忙，已合并 {self._queue_drops} 条过期请求；后续字幕仍会继续处理"
        if self.queue_size:
            return f"AI 回复排队中：{self.queue_size} 条"
        return ""

    def submit(self, event: CaptionEvent, *, record_event: bool = True) -> str:
        if self._closed:
            raise RuntimeError("回复引擎已关闭")
        existing = next(
            (turn for turn in self.conversation.turns if turn.event.event_id == event.event_id),
            None,
        )
        if existing is not None:
            if existing.event.source_text == event.source_text and (
                existing.event.translated_text == event.translated_text
            ):
                with self._lock:
                    current = self._latest_requests.get(event.event_id)
                if current is not None:
                    return current
            else:
                self.revise_event(event)
        elif record_event:
            self.conversation.add_event(event)
            self._persist_event(event)
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
            previous_sequence = self._event_sequences.get(event.event_id)
            if previous_sequence is not None and previous_sequence >= self._next_delivery:
                self._skipped.add(previous_sequence)
            self._latest_requests[event.event_id] = request.request_id
            while len(self._latest_requests) > 512:
                removed, _ = self._latest_requests.popitem(last=False)
                self._event_sequences.pop(removed, None)
            self._sequence += 1
            self._event_sequences[event.event_id] = self._sequence
            job = _Job(self._sequence, self.conversation.generation, request)
            try:
                self._jobs.put_nowait(job)
            except queue.Full:
                try:
                    discarded = self._jobs.get_nowait()
                    if discarded is not None:
                        self._skipped.add(discarded.sequence)
                        self._queue_drops += 1
                    self._jobs.task_done()
                except queue.Empty:
                    pass
                self._jobs.put_nowait(job)
        return request.request_id

    def record_event(self, event: CaptionEvent) -> None:
        self.conversation.add_event(event)
        self._persist_event(event)

    def invalidate_event(self, event_id: str) -> None:
        if event_id in self._latest_requests:
            self._latest_requests[event_id] = None
            sequence = self._event_sequences.get(event_id)
            if sequence is not None and sequence >= self._next_delivery:
                self._skipped.add(sequence)

    def revise_event(self, event: CaptionEvent) -> None:
        for turn in self.conversation.turns:
            if turn.event.event_id != event.event_id:
                continue
            if turn.event.source_text != event.source_text:
                turn.suggestion = None
                self.invalidate_event(event.event_id)
            turn.event = event
            if self.history is not None:
                try:
                    if turn.suggestion:
                        self.history.save(self.conversation.session_id, event, turn.suggestion)
                    else:
                        self.history.save_event(self.conversation.session_id, event)
                except StorageError:
                    LOGGER.warning("History revision save failed")
            return

    def drain_results(self) -> list[EngineResult]:
        while True:
            try:
                result = self._results.get_nowait()
            except queue.Empty:
                break
            if result.sequence >= self._next_delivery:
                self._completed[result.sequence] = result
        delivered: list[EngineResult] = []
        while True:
            if self._next_delivery in self._skipped:
                self._skipped.remove(self._next_delivery)
                self._completed.pop(self._next_delivery, None)
                self._next_delivery += 1
                continue
            result = self._completed.pop(self._next_delivery, None)
            if result is None:
                break
            self._next_delivery += 1
            if (
                result.generation != self.conversation.generation
                or result.request.session_id != self.conversation.session_id
                or self._latest_requests.get(result.request.event.event_id)
                != result.request.request_id
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
                            next((t.event for t in self.conversation.turns
                                  if t.event.event_id == result.request.event.event_id),
                                 result.request.event),
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

    def _persist_event(self, event: CaptionEvent) -> None:
        if self.history is None:
            return
        try:
            self.history.save_event(self.conversation.session_id, event)
        except StorageError:
            LOGGER.warning("History event save failed for event %s", event.event_id)

    def _worker(self) -> None:
        while not self._closed:
            try:
                job = self._jobs.get(timeout=0.2)
            except queue.Empty:
                continue
            if job is None:
                self._jobs.task_done()
                return
            if (job.generation != self.conversation.generation
                    or self._latest_requests.get(job.request.event.event_id)
                    != job.request.request_id):
                self._put_result(EngineResult(job.sequence, job.generation, job.request))
                self._jobs.task_done()
                continue
            try:
                suggestion = self.provider.generate(job.request)
                result = EngineResult(job.sequence, job.generation, job.request, suggestion)
            except Exception as exc:
                if isinstance(exc, LLMError):
                    LOGGER.warning(
                        "AI provider failed for request %s: kind=%s status=%s message=%s",
                        job.request.request_id,
                        exc.kind.value,
                        exc.status_code if exc.status_code is not None else "none",
                        str(exc)[:300],
                    )
                else:
                    LOGGER.warning(
                        "AI provider failed for request %s (%s)",
                        job.request.request_id,
                        type(exc).__name__,
                    )
                result = EngineResult(
                    job.sequence,
                    job.generation,
                    job.request,
                    error=str(exc) if isinstance(exc, LLMError) else "AI request failed",
                    error_kind=exc.kind if isinstance(exc, LLMError) else None,
                )
            self._put_result(result)
            self._jobs.task_done()

    def _put_result(self, result: EngineResult) -> None:
        """Keep result delivery bounded while preserving the delivery cursor."""
        try:
            self._results.put_nowait(result)
        except queue.Full:
            try:
                discarded = self._results.get_nowait()
                self._results.task_done()
                with self._lock:
                    if discarded.sequence >= self._next_delivery:
                        self._skipped.add(discarded.sequence)
            except queue.Empty:
                pass
            try:
                self._results.put_nowait(result)
            except queue.Full:
                with self._lock:
                    if result.sequence >= self._next_delivery:
                        self._skipped.add(result.sequence)


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
