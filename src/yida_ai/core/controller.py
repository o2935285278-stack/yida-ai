from __future__ import annotations

from dataclasses import dataclass

from yida_ai.adapters.captions.base import CaptionSource, CaptionSourceUnavailable
from yida_ai.core.captions import CaptionAssembler
from yida_ai.core.engine import EngineResult, ReplyEngine, should_generate
from yida_ai.core.models import CaptionEvent


@dataclass(frozen=True, slots=True)
class ControllerUpdate:
    captions: tuple[CaptionEvent, ...] = ()
    results: tuple[EngineResult, ...] = ()
    errors: tuple[str, ...] = ()


class ApplicationController:
    def __init__(
        self,
        source: CaptionSource,
        assembler: CaptionAssembler,
        engine: ReplyEngine,
        *,
        reply_mode: str = "every",
    ) -> None:
        self.source = source
        self.assembler = assembler
        self.engine = engine
        self.reply_mode = reply_mode
        self.paused = False
        self.pending_confirmation: dict[str, CaptionEvent] = {}

    def tick(self, now: float | None = None) -> ControllerUpdate:
        captions: list[CaptionEvent] = []
        errors: list[str] = []
        if not self.paused:
            try:
                incoming = self.source.poll()
            except CaptionSourceUnavailable as exc:
                incoming = []
                errors.append(str(exc))
            for event in incoming:
                captions.extend(self.assembler.accept(event, now=now))
            captions.extend(self.assembler.flush_ready(now=now))
            for event in captions:
                self._record_or_generate(event)
        results = self.engine.drain_results()
        return ControllerUpdate(tuple(captions), tuple(results), tuple(errors))

    def flush(self) -> ControllerUpdate:
        captions = self.assembler.flush()
        for event in captions:
            self._record_or_generate(event)
        return ControllerUpdate(tuple(captions), tuple(self.engine.drain_results()), ())

    def confirm(self, event_id: str) -> str:
        event = self.pending_confirmation.pop(event_id)
        return self.engine.submit(event, record_event=False)

    def toggle_pause(self) -> bool:
        self.paused = not self.paused
        return self.paused

    def clear_session(self) -> None:
        self.assembler.clear()
        self.pending_confirmation.clear()
        self.engine.clear_session()

    def close(self) -> None:
        self.source.close()
        self.engine.shutdown()

    def _record_or_generate(self, event: CaptionEvent) -> None:
        if self.reply_mode == "confirm":
            self.engine.conversation.add_event(event)
            self.pending_confirmation[event.event_id] = event
        elif should_generate(self.reply_mode, event):
            self.engine.submit(event)
        else:
            self.engine.conversation.add_event(event)
