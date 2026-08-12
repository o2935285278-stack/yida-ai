from __future__ import annotations

import json
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from yida_ai.core.models import CaptionEvent, EvidenceStatus, ReplyRequest, ReplySuggestion
from yida_ai.providers.llm.base import (
    LLMConfigurationError,
    LLMError,
    LLMErrorKind,
    LLMProvider,
)
from yida_ai.providers.llm.prompt import build_messages


@dataclass(frozen=True, slots=True)
class OpenAICompatibleConfig:
    api_url: str
    api_key: str
    model: str
    timeout_seconds: float = 12.0
    max_tokens: int = 600
    temperature: float = 0.2
    retry_limit: int = 1


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, config: OpenAICompatibleConfig) -> None:
        self.config = config

    @property
    def provider_name(self) -> str:
        hostname = _hostname(self.config.api_url)
        if hostname == "api.deepseek.com" or hostname.endswith(".api.deepseek.com"):
            return "DeepSeek (OpenAI-compatible)"
        if hostname == "api.openai.com" or hostname.endswith(".api.openai.com"):
            return "OpenAI"
        return hostname or "OpenAI-compatible"

    def generate(self, request: ReplyRequest) -> ReplySuggestion:
        self._validate()
        payload: dict[str, object] = {
            "model": self.config.model,
            "messages": build_messages(request),
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        if _uses_official_deepseek_api(self.config.api_url):
            payload["thinking"] = {"type": "disabled"}

        last_error: LLMError | None = None
        for attempt in range(self.config.retry_limit + 1):
            try:
                parsed = self._post_json(payload)
                return _suggestion_from_payload(request, parsed)
            except LLMError as exc:
                last_error = exc
                if isinstance(exc, LLMEmptyResponseError):
                    payload.pop("response_format", None)
                if attempt >= self.config.retry_limit or not _is_retryable(exc):
                    break
                time.sleep(min(0.25 * (attempt + 1), 0.75))
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                last_error = LLMError(
                    "AI 返回的数据格式无效，请检查接口是否兼容 OpenAI Chat Completions",
                    kind=LLMErrorKind.INVALID_RESPONSE,
                )
                if attempt >= self.config.retry_limit:
                    break
                time.sleep(min(0.25 * (attempt + 1), 0.75))

        assert last_error is not None
        retry_suffix = f"（已重试 {self.config.retry_limit} 次）" if self.config.retry_limit else ""
        raise LLMError(
            f"{last_error}{retry_suffix}",
            kind=last_error.kind,
            status_code=last_error.status_code,
        ) from last_error

    def test_connection(self) -> tuple[str, str]:
        """Run a harmless request through the same path used for real replies."""
        event = CaptionEvent(
            source_text="Connection test: reply briefly.",
            translated_text="连接测试：请简短回复。",
            source_language="en-US",
            translated_language="zh-CN",
            source="connection-test",
        )
        request = ReplyRequest(
            event=event,
            context=(event,),
            citations=(),
            scene="general",
            user_language="zh-CN",
            reply_language="en-US",
            reply_length="short",
            session_id="connection-test",
        )
        self.generate(request)
        return self.provider_name, self.config.model

    def _validate(self) -> None:
        if not self.config.api_url.strip():
            raise LLMConfigurationError("尚未配置 OpenAI-compatible API 地址")
        if not self.config.model.strip():
            raise LLMConfigurationError("尚未配置模型名称")
        if not self.config.api_key.strip():
            raise LLMConfigurationError(
                "没有填写或加载 API Key，请在设置中填写后选择安全保存",
                kind=LLMErrorKind.MISSING_KEY,
            )

    def _post_json(self, payload: dict[str, object]) -> dict[str, object]:
        request = urllib.request.Request(
            self.config.api_url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                raw_body = response.read().decode("utf-8", errors="replace")
                if not raw_body.strip():
                    raise LLMEmptyResponseError("AI 服务返回了空响应")
                try:
                    body = json.loads(raw_body)
                except json.JSONDecodeError as exc:
                    raise LLMError(
                        "AI 服务返回了无效 JSON，请检查 API 地址和兼容性",
                        kind=LLMErrorKind.INVALID_RESPONSE,
                    ) from exc
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", errors="replace")
            finally:
                exc.close()
            raise _http_error(exc.code, detail, self.config.api_key) from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise LLMError(
                    f"AI 请求超时（{self.config.timeout_seconds:g} 秒），字幕与翻译仍会继续运行",
                    kind=LLMErrorKind.TIMEOUT,
                ) from exc
            reason = _safe_detail(str(exc.reason), self.config.api_key)
            raise LLMError(f"无法连接 AI 服务：{reason}", kind=LLMErrorKind.NETWORK) from exc
        except TimeoutError as exc:
            raise LLMError(
                f"AI 请求超时（{self.config.timeout_seconds:g} 秒），字幕与翻译仍会继续运行",
                kind=LLMErrorKind.TIMEOUT,
            ) from exc

        try:
            choice = body["choices"][0]
            message = choice["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(
                "AI 返回数据缺少 choices[0].message，请检查接口兼容性",
                kind=LLMErrorKind.INVALID_RESPONSE,
            ) from exc
        raw_content = message.get("content")
        content = "" if raw_content is None else str(raw_content).strip()
        if not content:
            if choice.get("finish_reason") == "length":
                raise LLMEmptyResponseError("AI 输出达到长度上限，未生成最终回复")
            raise LLMEmptyResponseError("AI 服务返回了空内容")
        if content.startswith("```"):
            content = (
                content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            )
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMError(
                "AI 回答不是有效 JSON；已保留字幕，可重试或检查模型兼容性",
                kind=LLMErrorKind.INVALID_RESPONSE,
            ) from exc
        if not isinstance(parsed, dict):
            raise LLMError(
                "AI 回答 JSON 顶层不是对象",
                kind=LLMErrorKind.INVALID_RESPONSE,
            )
        return parsed


class LLMEmptyResponseError(LLMError):
    """A successful HTTP response that contains no usable assistant content."""

    def __init__(self, message: str) -> None:
        super().__init__(message, kind=LLMErrorKind.INVALID_RESPONSE)


def _hostname(api_url: str) -> str:
    try:
        return (urllib.parse.urlparse(api_url).hostname or "").casefold()
    except ValueError:
        return ""


def _uses_official_deepseek_api(api_url: str) -> bool:
    hostname = _hostname(api_url)
    return hostname == "api.deepseek.com" or hostname.endswith(".api.deepseek.com")


def _is_retryable(error: LLMError) -> bool:
    return error.kind in {
        LLMErrorKind.TIMEOUT,
        LLMErrorKind.NETWORK,
        LLMErrorKind.RATE_LIMITED,
        LLMErrorKind.SERVER_ERROR,
        LLMErrorKind.INVALID_RESPONSE,
        LLMErrorKind.UNKNOWN,
    }


def _safe_detail(value: str, api_key: str, limit: int = 240) -> str:
    cleaned = value.replace(api_key, "[REDACTED]") if api_key else value
    cleaned = re.sub(r"(?i)bearer\s+[A-Za-z0-9._~+\-/]+=*", "Bearer [REDACTED]", cleaned)
    cleaned = re.sub(r"\bsk-[A-Za-z0-9_-]{8,}\b", "[REDACTED]", cleaned)
    return " ".join(cleaned.split())[:limit] or "未提供错误详情"


def _http_error(status_code: int, detail: str, api_key: str) -> LLMError:
    safe = _safe_detail(detail, api_key)
    if status_code in {401, 403}:
        return LLMError(
            f"API Key 无效或无权限（HTTP {status_code}）",
            kind=LLMErrorKind.INVALID_KEY,
            status_code=status_code,
        )
    if status_code == 404:
        return LLMError(
            "API 地址或模型不存在（HTTP 404），请检查端点和模型名称",
            kind=LLMErrorKind.MODEL_NOT_FOUND,
            status_code=status_code,
        )
    if status_code == 429:
        return LLMError(
            "AI 服务额度不足或请求过于频繁（HTTP 429），请稍后重试或检查账户额度",
            kind=LLMErrorKind.RATE_LIMITED,
            status_code=status_code,
        )
    if 500 <= status_code <= 599:
        return LLMError(
            f"AI 服务端暂时异常（HTTP {status_code}）：{safe}",
            kind=LLMErrorKind.SERVER_ERROR,
            status_code=status_code,
        )
    return LLMError(
        f"AI 服务请求失败（HTTP {status_code}）：{safe}",
        kind=LLMErrorKind.UNKNOWN,
        status_code=status_code,
    )


def _suggestion_from_payload(request: ReplyRequest, payload: dict[str, object]) -> ReplySuggestion:
    required = ("current_question", "suggested_reply", "translated_reply")
    if not all(isinstance(payload.get(key), str) and str(payload[key]).strip() for key in required):
        raise LLMError(
            "AI 返回数据缺少必要字段",
            kind=LLMErrorKind.INVALID_RESPONSE,
        )
    try:
        evidence = EvidenceStatus(str(payload.get("evidence_status", "not_found")))
    except ValueError:
        evidence = EvidenceStatus.NOT_FOUND
    suggested_reply = str(payload["suggested_reply"]).strip()
    translated_reply = str(payload["translated_reply"]).strip()
    if not request.citations and evidence is EvidenceStatus.DOCUMENTED:
        evidence = EvidenceStatus.NOT_FOUND
        suggested_reply = "资料中没有明确答案，也没有足够依据，请确认后再作答。"
        translated_reply = (
            "The documents do not contain enough evidence. Please verify before replying."
        )
    return ReplySuggestion(
        request_id=request.request_id,
        event_id=request.event.event_id,
        current_question=str(payload["current_question"]).strip(),
        suggested_reply=suggested_reply,
        translated_reply=translated_reply,
        citations=request.citations,
        evidence_status=evidence,
    )
