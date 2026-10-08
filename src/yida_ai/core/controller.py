from __future__ import annotations

import time
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
        self._stable: dict[str, tuple[CaptionEvent, float]] = {}
        self._source_epoch = None

    def _sync_epoch(self, epoch) -> None:
        if epoch == self._source_epoch:
            return
        self._source_epoch = epoch
        self.assembler.clear()
        self._stable.clear()
        self.pending_confirmation.clear()
        # A new source connection starts a new conversation generation.  The
        # engine also drops queued work, so results from the old connection
        # cannot be delivered after recovery.
        self.engine.clear_session()

    def tick(self, now: float | None = None) -> ControllerUpdate:
        captions: list[CaptionEvent] = []
        errors: list[str] = []
        clock = time.monotonic() if now is None else now
        if not self.paused:
            self._sync_epoch(getattr(self.source, "epoch", self._source_epoch))
            try:
                incoming = self.source.poll()
            except CaptionSourceUnavailable as exc:
                incoming = []
                errors.append(str(exc))
            current_epoch = getattr(self.source, "epoch", self._source_epoch)
            if current_epoch != self._source_epoch:
                self._sync_epoch(current_epoch)
            incoming = [
                event for event in incoming
                if event.metadata.get("epoch", self._source_epoch) == self._source_epoch
            ]
            for event in incoming:
                event_epoch = event.metadata.get("epoch")
                if event_epoch is not None and event_epoch != self._source_epoch:
                    # A reconnect can leave already-read packets in the pipe.
                    # Never let an event from the previous epoch reopen state.
                    continue
                if event.source in {"windows-captions", "translation-program"} or (
                    event.revision_of == event.event_id
                ):
                    captions.append(event)
                    continue
                captions.extend(self.assembler.accept(event, now=clock))
            captions.extend(self.assembler.flush_ready(now=clock))
            for event in captions:
                if event.source == "translation-program":
                    self._accept_stream(event, clock)
                    continue
                if event.revision_of == event.event_id:
                    self.engine.revise_event(event)
                    continue
                self._record_or_generate(event)
            for event_id, (event, changed) in list(self._stable.items()):
                if clock - changed >= .7:
                    self._stable.pop(event_id)
                    if should_generate(self.reply_mode, event):
                        self.engine.submit(event, record_event=False)
        results = self.engine.drain_results()
        return ControllerUpdate(tuple(captions), tuple(results), tuple(errors))

    def flush(self) -> ControllerUpdate:
        captions = self.assembler.flush()
        for event in captions:
            self._record_or_generate(event)
        return ControllerUpdate(tuple(captions), tuple(self.engine.drain_results()), ())

    def confirm(self, event_id: str) -> str:
        event = self.pending_confirmation.pop(event_id)
        self._stable.pop(event_id, None)
        return self.engine.submit(event, record_event=False)

    def _accept_stream(self, event: CaptionEvent, now: float) -> None:
        epoch = event.metadata.get("epoch")
        if epoch != self._source_epoch:
            self._sync_epoch(epoch)
        previous = next((t for t in self.engine.conversation.turns
                         if t.event.event_id == event.event_id), None)
        changed = previous is None or previous.event.source_text != event.source_text
        if previous:
            self.engine.revise_event(event)
        else:
            self.engine.record_event(event)
        if changed:
            self.engine.invalidate_event(event.event_id)
            if not event.metadata.get("replay"):
                self._stable[event.event_id] = (event, now)
        elif event.event_id in self._stable:
            self._stable[event.event_id] = (event, self._stable[event.event_id][1])
        self.pending_confirmation[event.event_id] = event
        keep = {t.event.event_id for t in self.engine.conversation.turns}
        self.pending_confirmation = {
            k: v for k, v in self.pending_confirmation.items() if k in keep
        }
        self._stable = {k: v for k, v in self._stable.items() if k in keep}

    def toggle_pause(self) -> bool:
        self.paused = not self.paused
        return self.paused

    def clear_session(self) -> None:
        self.assembler.clear()
        self.pending_confirmation.clear()
        self._stable.clear()
        self.engine.clear_session()

    def close(self) -> None:
        self.source.close()
        self.engine.shutdown()

    def _record_or_generate(self, event: CaptionEvent) -> None:
        if self.reply_mode == "confirm":
            self.engine.record_event(event)
            self.pending_confirmation[event.event_id] = event
        elif should_generate(self.reply_mode, event):
            self.engine.submit(event)
        else:
            self.engine.record_event(event)
