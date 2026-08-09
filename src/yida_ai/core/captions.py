from __future__ import annotations

import re
import time
from collections import deque
from dataclasses import replace

from yida_ai.core.models import CaptionEvent

_SPACE_RE = re.compile(r"\s+")
_TERMINAL = (".", "?", "!", "。", "？", "！", "…")
_CONNECTORS = (
    "and ",
    "but ",
    "because ",
    "so ",
    "e ",
    "mas ",
    "porque ",
    "então ",
    "而且",
    "但是",
    "因为",
    "所以",
)


def normalize_text(text: str) -> str:
    return _SPACE_RE.sub(" ", text).strip()


def caption_key(text: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", normalize_text(text).lower())


class CaptionAssembler:
    def __init__(self, settle_seconds: float = 0.6, duplicate_window: float = 12.0) -> None:
        self.settle_seconds = settle_seconds
        self.duplicate_window = duplicate_window
        self.pending: CaptionEvent | None = None
        self.pending_at = 0.0
        self.recent: deque[tuple[float, str, str]] = deque(maxlen=64)

    def accept(self, event: CaptionEvent, now: float | None = None) -> list[CaptionEvent]:
        current = time.monotonic() if now is None else now
        event = replace(
            event,
            source_text=normalize_text(event.source_text),
            translated_text=normalize_text(event.translated_text),
        )
        if not event.source_text:
            return []
        if self._is_duplicate(event, current):
            return []
        if self.pending is None:
            self.pending = event
            self.pending_at = current
            return []
        if self._is_revision(self.pending, event):
            if len(caption_key(event.source_text)) >= len(caption_key(self.pending.source_text)):
                self.pending = replace(event, revision_of=self.pending.event_id)
            self.pending_at = current
            return []
        if self._should_merge(self.pending, event):
            self.pending = replace(
                event,
                source_text=f"{self.pending.source_text} {event.source_text}".strip(),
                translated_text=(f"{self.pending.translated_text} {event.translated_text}".strip()),
                revision_of=self.pending.event_id,
            )
            self.pending_at = current
            return []
        finalized = self._take_pending(current)
        self.pending = event
        self.pending_at = current
        return [finalized] if finalized else []

    def flush_ready(self, now: float | None = None) -> list[CaptionEvent]:
        current = time.monotonic() if now is None else now
        if self.pending is None or current - self.pending_at < self.settle_seconds:
            return []
        event = self._take_pending(current)
        return [event] if event else []

    def flush(self, now: float | None = None) -> list[CaptionEvent]:
        event = self._take_pending(time.monotonic() if now is None else now)
        return [event] if event else []

    def clear(self) -> None:
        self.pending = None
        self.recent.clear()

    def _take_pending(self, now: float) -> CaptionEvent | None:
        event = self.pending
        self.pending = None
        if event is not None:
            self.recent.append(
                (now, caption_key(event.source_text), caption_key(event.translated_text))
            )
        return event

    def _is_duplicate(self, event: CaptionEvent, now: float) -> bool:
        source = caption_key(event.source_text)
        translated = caption_key(event.translated_text)
        while self.recent and now - self.recent[0][0] > self.duplicate_window:
            self.recent.popleft()
        return any(
            source == old_source and translated == old_translation
            for _, old_source, old_translation in self.recent
        )

    @staticmethod
    def _is_revision(previous: CaptionEvent, current: CaptionEvent) -> bool:
        old = caption_key(previous.source_text)
        new = caption_key(current.source_text)
        return bool(old and new and (old == new or old.startswith(new) or new.startswith(old)))

    @staticmethod
    def _should_merge(previous: CaptionEvent, current: CaptionEvent) -> bool:
        previous_text = previous.source_text.rstrip()
        current_text = current.source_text.lower().lstrip()
        return not previous_text.endswith(_TERMINAL) and (
            len(previous_text) < 180 or current_text.startswith(_CONNECTORS)
        )
