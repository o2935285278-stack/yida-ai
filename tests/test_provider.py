import urllib.error

import pytest

from yida_ai.core.models import CaptionEvent, ReplyRequest
from yida_ai.providers.llm.base import LLMConfigurationError, LLMError
from yida_ai.providers.llm.openai_compatible import (
    OpenAICompatibleConfig,
    OpenAICompatibleProvider,
)


def _request():
    event = CaptionEvent(source_text="Hello?", translated_text="你好？")
    return ReplyRequest(event, (event,), (), "general", "zh-CN", "en-US", "short", "s")


def _provider(**overrides):
    values = {
        "api_url": "https://invalid.example/v1/chat/completions",
        "api_key": "dummy",
        "model": "mock",
    }
    values.update(overrides)
    return OpenAICompatibleProvider(OpenAICompatibleConfig(**values))


def test_api_key_missing_is_clear():
    provider = _provider(api_key="")
    with pytest.raises(LLMConfigurationError, match="API Key"):
        provider.generate(_request())


def test_provider_parses_mocked_response(monkeypatch):
    provider = _provider()
    monkeypatch.setattr(
        provider,
        "_post_json",
        lambda payload: {
            "current_question": "你好？",
            "suggested_reply": "您好。",
            "translated_reply": "Hello.",
            "evidence_status": "not_found",
        },
    )
    assert provider.generate(_request()).translated_reply == "Hello."


def test_provider_blocks_unsupported_document_claim(monkeypatch):
    provider = _provider()
    monkeypatch.setattr(
        provider,
        "_post_json",
        lambda payload: {
            "current_question": "营收是多少？",
            "suggested_reply": "营收是五百万元。",
            "translated_reply": "Revenue was five million.",
            "evidence_status": "documented",
        },
    )
    result = provider.generate(_request())
    assert "没有明确答案" in result.suggested_reply
    assert result.evidence_status.value == "not_found"


def test_request_failure_has_limited_retry(monkeypatch):
    provider = _provider(retry_limit=2)
    calls = 0

    def fail(payload):
        nonlocal calls
        calls += 1
        raise LLMError("offline")

    monkeypatch.setattr(provider, "_post_json", fail)
    monkeypatch.setattr("yida_ai.providers.llm.openai_compatible.time.sleep", lambda _: None)
    with pytest.raises(LLMError, match="已重试 2 次"):
        provider.generate(_request())
    assert calls == 3


@pytest.mark.parametrize(
    ("reason", "message"),
    [(TimeoutError("slow"), "超时"), (OSError("offline"), "无法连接")],
)
def test_timeout_and_offline_errors(monkeypatch, reason, message):
    provider = _provider(retry_limit=0)

    def fail(*args, **kwargs):
        raise urllib.error.URLError(reason)

    monkeypatch.setattr("urllib.request.urlopen", fail)
    with pytest.raises(LLMError, match=message):
        provider.generate(_request())
