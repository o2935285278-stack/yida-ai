from __future__ import annotations

from yida_ai.core.models import EvidenceStatus, ReplyRequest, ReplySuggestion
from yida_ai.providers.llm.base import LLMProvider


class MockLLMProvider(LLMProvider):
    """Deterministic provider for tests, demos and offline use."""

    def __init__(self, *, fail: Exception | None = None) -> None:
        self.fail = fail
        self.requests: list[ReplyRequest] = []

    def generate(self, request: ReplyRequest) -> ReplySuggestion:
        self.requests.append(request)
        if self.fail:
            raise self.fail
        if request.citations:
            evidence = EvidenceStatus.DOCUMENTED
            fact = request.citations[0].excerpt.splitlines()[0][:120]
            suggested = f"根据资料：{fact}"
        else:
            evidence = EvidenceStatus.NOT_FOUND
            suggested = "资料中没有明确答案，请确认后再作答。"
        return ReplySuggestion(
            request_id=request.request_id,
            event_id=request.event.event_id,
            current_question=request.event.translated_text or request.event.source_text,
            suggested_reply=suggested,
            translated_reply=f"[{request.reply_language}] {suggested}",
            citations=request.citations,
            evidence_status=evidence,
        )
