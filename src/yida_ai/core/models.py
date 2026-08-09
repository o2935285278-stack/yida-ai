from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class EvidenceStatus(StrEnum):
    DOCUMENTED = "documented"
    INFERRED = "inferred"
    NOT_FOUND = "not_found"


@dataclass(frozen=True, slots=True)
class CaptionEvent:
    source_text: str
    translated_text: str = ""
    source_language: str = "auto"
    translated_language: str = ""
    source: str = "unknown"
    event_id: str = field(default_factory=lambda: new_id("caption"))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    is_final: bool = True
    revision_of: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class KnowledgeCitation:
    document_id: str
    document_name: str
    excerpt: str
    score: float
    chunk_id: str


@dataclass(frozen=True, slots=True)
class ReplyRequest:
    event: CaptionEvent
    context: tuple[CaptionEvent, ...]
    citations: tuple[KnowledgeCitation, ...]
    scene: str
    user_language: str
    reply_language: str
    reply_length: str
    session_id: str
    scene_instruction: str = ""
    request_id: str = field(default_factory=lambda: new_id("request"))


@dataclass(frozen=True, slots=True)
class ReplySuggestion:
    request_id: str
    event_id: str
    current_question: str
    suggested_reply: str
    translated_reply: str
    citations: tuple[KnowledgeCitation, ...] = ()
    evidence_status: EvidenceStatus = EvidenceStatus.NOT_FOUND
    error: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class ConversationTurn:
    event: CaptionEvent
    suggestion: ReplySuggestion | None = None
    turn_id: str = field(default_factory=lambda: new_id("turn"))
