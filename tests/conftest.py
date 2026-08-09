from __future__ import annotations

from datetime import UTC, datetime

import pytest

from yida_ai.core.models import CaptionEvent, EvidenceStatus, ReplySuggestion


@pytest.fixture
def event_factory():
    def make(event_id: str = "event-1", text: str = "Hello?", translated: str = "你好？"):
        return CaptionEvent(
            event_id=event_id,
            source_text=text,
            translated_text=translated,
            source_language="en-US",
            translated_language="zh-CN",
            source="test",
            occurred_at=datetime(2026, 1, 2, tzinfo=UTC),
        )

    return make


@pytest.fixture
def suggestion_factory():
    def make(event_id: str = "event-1"):
        return ReplySuggestion(
            request_id="request-1",
            event_id=event_id,
            current_question="你好？",
            suggested_reply="您好。",
            translated_reply="Hello.",
            evidence_status=EvidenceStatus.NOT_FOUND,
        )

    return make
