import io
import urllib.error

import pytest

from yida_ai.core.models import CaptionEvent, ReplyRequest
from yida_ai.providers.llm.base import LLMConfigurationError, LLMError, LLMErrorKind
from yida_ai.providers.llm.openai_compatible import (
    LLMEmptyResponseError,
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


def test_official_deepseek_disables_thinking(monkeypatch):
    provider = _provider(
        api_url="https://api.deepseek.com/v1/chat/completions",
        model="deepseek-v4-flash",
    )
    captured = {}

    def respond(payload):
        captured.update(payload)
        return {
            "current_question": "你好？",
            "suggested_reply": "您好。",
            "translated_reply": "Hello.",
            "evidence_status": "not_found",
        }

    monkeypatch.setattr(provider, "_post_json", respond)
    provider.generate(_request())
    assert captured["thinking"] == {"type": "disabled"}


def test_empty_json_content_retries_without_response_format(monkeypatch):
    provider = _provider(retry_limit=1)
    payloads = []

    def respond(payload):
        payloads.append(dict(payload))
        if len(payloads) == 1:
            raise LLMEmptyResponseError("AI 服务返回了空内容")
        return {
            "current_question": "你好？",
            "suggested_reply": "您好。",
            "translated_reply": "Hello.",
            "evidence_status": "not_found",
        }

    monkeypatch.setattr(provider, "_post_json", respond)
    monkeypatch.setattr("yida_ai.providers.llm.openai_compatible.time.sleep", lambda _: None)
    assert provider.generate(_request()).translated_reply == "Hello."
    assert "response_format" in payloads[0]
    assert "response_format" not in payloads[1]


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


@pytest.mark.parametrize(
    ("status", "kind", "message"),
    [
        (401, LLMErrorKind.INVALID_KEY, "API Key 无效"),
        (404, LLMErrorKind.MODEL_NOT_FOUND, "模型不存在"),
        (429, LLMErrorKind.RATE_LIMITED, "额度不足"),
        (503, LLMErrorKind.SERVER_ERROR, "服务端"),
    ],
)
def test_http_errors_are_classified_and_redacted(monkeypatch, status, kind, message):
    secret = "fixture-sensitive-value"
    provider = _provider(api_key=secret, retry_limit=0)
    bodies = []

    def fail(*args, **kwargs):
        body = io.BytesIO(f'{{"error":"Bearer {secret}"}}'.encode())
        bodies.append(body)
        raise urllib.error.HTTPError(provider.config.api_url, status, "failure", {}, body)

    monkeypatch.setattr("urllib.request.urlopen", fail)
    with pytest.raises(LLMError, match=message) as captured:
        provider.generate(_request())
    assert captured.value.kind is kind
    assert captured.value.status_code == status
    assert secret not in str(captured.value)
    assert bodies[0].closed


def test_invalid_json_response_is_clear(monkeypatch):
    provider = _provider(retry_limit=0)

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b"not-json"

    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: Response())
    with pytest.raises(LLMError, match="无效 JSON") as captured:
        provider.generate(_request())
    assert captured.value.kind is LLMErrorKind.INVALID_RESPONSE
