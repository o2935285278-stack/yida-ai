from __future__ import annotations

import time

import pytest

from yida_ai.adapters.captions.mock import MockCaptionSource
from yida_ai.core.captions import CaptionAssembler
from yida_ai.core.controller import ApplicationController
from yida_ai.core.conversation import ConversationManager
from yida_ai.core.engine import ReplyEngine, should_generate
from yida_ai.core.models import EvidenceStatus, ReplySuggestion
from yida_ai.providers.llm.base import LLMProvider
from yida_ai.providers.llm.mock import MockLLMProvider
from yida_ai.retrieval.keyword import KeywordRetriever
from yida_ai.storage.history import HistoryStore


class DelayedProvider(LLMProvider):
    def __init__(self, delays=None, fail=False):
        self.delays = delays or {}
        self.fail = fail

    def generate(self, request):
        time.sleep(self.delays.get(request.event.event_id, 0))
        if self.fail:
            raise RuntimeError("simulated provider failure")
        return ReplySuggestion(
            request_id=request.request_id,
            event_id=request.event.event_id,
            current_question=request.event.source_text,
            suggested_reply=f"reply-{request.event.event_id}",
            translated_reply=f"translated-{request.event.event_id}",
            evidence_status=EvidenceStatus.NOT_FOUND,
        )


def _engine(provider, *, workers=2, max_queue=4):
    return ReplyEngine(
        provider,
        KeywordRetriever(),
        ConversationManager(15),
        workers=workers,
        max_queue=max_queue,
    )


def _wait_results(engine, count, timeout=2):
    deadline = time.monotonic() + timeout
    output = []
    while time.monotonic() < deadline and len(output) < count:
        output.extend(engine.drain_results())
        time.sleep(0.01)
    return output


def test_multiple_results_are_delivered_in_request_order(event_factory):
    engine = _engine(DelayedProvider({"one": 0.12, "two": 0.01}))
    try:
        engine.submit(event_factory("one", "First?"))
        engine.submit(event_factory("two", "Second?"))
        results = _wait_results(engine, 2)
        assert [item.request.event.event_id for item in results] == ["one", "two"]
    finally:
        engine.shutdown()


def test_clear_session_discards_stale_result(event_factory):
    engine = _engine(DelayedProvider({"old": 0.08}), workers=1)
    try:
        engine.submit(event_factory("old"))
        engine.clear_session()
        time.sleep(0.15)
        assert engine.drain_results() == []
    finally:
        engine.shutdown()


def test_slow_or_failed_ai_does_not_block_caption_polling(event_factory):
    source = MockCaptionSource([event_factory("slow")])
    engine = _engine(DelayedProvider({"slow": 0.2}))
    controller = ApplicationController(source, CaptionAssembler(settle_seconds=0), engine)
    try:
        started = time.monotonic()
        update = controller.tick(now=1)
        elapsed = time.monotonic() - started
        assert elapsed < 0.08
        assert update.captions
    finally:
        controller.close()


def test_provider_failure_returns_error_without_crashing(event_factory):
    engine = _engine(DelayedProvider(fail=True))
    try:
        engine.submit(event_factory("bad"))
        results = _wait_results(engine, 1)
        assert results[0].error == "simulated provider failure"
    finally:
        engine.shutdown()


def test_reply_modes_and_confirm_mode(event_factory):
    question = event_factory(text="Could you help?")
    statement = event_factory(text="Good morning.", translated="早上好。")
    assert not should_generate("translation", question)
    assert should_generate("every", statement)
    assert should_generate("auto", question)
    assert not should_generate("auto", statement)

    provider = MockLLMProvider()
    engine = _engine(provider)
    controller = ApplicationController(
        MockCaptionSource([question]),
        CaptionAssembler(settle_seconds=0),
        engine,
        reply_mode="confirm",
    )
    try:
        controller.tick(now=1)
        assert question.event_id in controller.pending_confirmation
        request_id = controller.confirm(question.event_id)
        assert request_id
        assert _wait_results(engine, 1)[0].suggestion is not None
    finally:
        controller.close()


def test_translation_mode_persists_caption_without_ai(tmp_path, event_factory):
    event = event_factory(text="A statement.", translated="一句陈述。")
    history = HistoryStore(tmp_path / "history.db")
    engine = ReplyEngine(
        MockLLMProvider(),
        KeywordRetriever(),
        ConversationManager(15),
        history,
    )
    controller = ApplicationController(
        MockCaptionSource([event]),
        CaptionAssembler(settle_seconds=0),
        engine,
        reply_mode="translation",
    )
    try:
        update = controller.tick(now=1)
        assert update.captions
        loaded = history.load_recent()
        assert loaded[0][1].event_id == event.event_id
        assert loaded[0][2] is None
    finally:
        controller.close()


def test_bounded_queue_discards_backlog_without_deadlock(event_factory):
    engine = _engine(DelayedProvider({"one": 0.15}), workers=1, max_queue=1)
    try:
        engine.submit(event_factory("one"))
        time.sleep(0.02)
        engine.submit(event_factory("two"))
        engine.submit(event_factory("three"))
        results = _wait_results(engine, 2)
        assert [result.request.event.event_id for result in results] == ["one", "three"]
    finally:
        engine.shutdown()


@pytest.mark.parametrize(
    ("source_language", "translation_language"),
    [
        ("zh-CN", "en-US"),
        ("zh-CN", "pt-BR"),
        ("en-US", "zh-CN"),
        ("en-US", "pt-BR"),
        ("pt-BR", "zh-CN"),
        ("pt-BR", "en-US"),
    ],
)
def test_six_translation_directions_complete_mock_flow(
    event_factory, source_language, translation_language
):
    event = event_factory(f"{source_language}-{translation_language}")
    event = type(event)(
        source_text=event.source_text,
        translated_text=event.translated_text,
        source_language=source_language,
        translated_language=translation_language,
        event_id=event.event_id,
    )
    engine = ReplyEngine(
        MockLLMProvider(),
        KeywordRetriever(),
        ConversationManager(15),
        user_language=translation_language,
        reply_language=source_language,
    )
    try:
        engine.submit(event)
        result = _wait_results(engine, 1)[0].suggestion
        assert result is not None
        assert result.event_id == event.event_id
        assert result.translated_reply.startswith(f"[{source_language}]")
    finally:
        engine.shutdown()
