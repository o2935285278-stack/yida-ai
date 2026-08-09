from __future__ import annotations

import json
from collections import deque
from collections.abc import Iterable
from pathlib import Path

from yida_ai.adapters.captions.base import CaptionSource, CaptionSourceStatus
from yida_ai.core.models import CaptionEvent


class MockCaptionSource(CaptionSource):
    def __init__(self, events: Iterable[CaptionEvent] = ()) -> None:
        self._events = deque(events)

    @classmethod
    def from_jsonl(cls, path: str | Path) -> MockCaptionSource:
        events: list[CaptionEvent] = []
        with Path(path).open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                payload = json.loads(line)
                payload.setdefault("event_id", f"mock-{line_number}")
                payload.setdefault("source", "mock")
                events.append(CaptionEvent(**payload))
        return cls(events)

    def push(self, event: CaptionEvent) -> None:
        self._events.append(event)

    @property
    def remaining(self) -> int:
        return len(self._events)

    def status(self) -> CaptionSourceStatus:
        return CaptionSourceStatus(True, "模拟字幕", f"等待事件：{len(self._events)}")

    def poll(self, limit: int = 50) -> list[CaptionEvent]:
        result: list[CaptionEvent] = []
        for _ in range(min(limit, len(self._events))):
            result.append(self._events.popleft())
        return result
