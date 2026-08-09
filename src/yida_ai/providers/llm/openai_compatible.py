from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from yida_ai.core.models import EvidenceStatus, ReplyRequest, ReplySuggestion
from yida_ai.providers.llm.base import LLMConfigurationError, LLMError, LLMProvider
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

    def generate(self, request: ReplyRequest) -> ReplySuggestion:
        self._validate()
        payload = {
            "model": self.config.model,
            "messages": build_messages(request),
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        last_error: Exception | None = None
        for attempt in range(self.config.retry_limit + 1):
            try:
                parsed = self._post_json(payload)
                return _suggestion_from_payload(request, parsed)
            except (LLMError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                last_error = exc
                if attempt >= self.config.retry_limit:
                    break
                time.sleep(min(0.25 * (attempt + 1), 0.75))
        raise LLMError(f"AI 请求失败（已重试 {self.config.retry_limit} 次）：{last_error}")

    def _validate(self) -> None:
        if not self.config.api_url.strip():
            raise LLMConfigurationError("尚未配置 OpenAI-compatible API 地址")
        if not self.config.model.strip():
            raise LLMConfigurationError("尚未配置模型名称")
        if not self.config.api_key.strip():
            raise LLMConfigurationError(
                "缺少 API Key。请设置环境变量 YIDA_AI_API_KEY；密钥不会保存进项目。"
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
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LLMError(f"AI 服务返回 HTTP {exc.code}: {detail[:160]}") from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise LLMError("AI 请求超时，字幕与翻译仍会继续运行") from exc
            raise LLMError(f"无法连接 AI 服务：{exc.reason}") from exc
        except TimeoutError as exc:
            raise LLMError("AI 请求超时，字幕与翻译仍会继续运行") from exc
        content = str(body["choices"][0]["message"]["content"]).strip()
        if content.startswith("```"):
            content = (
                content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            )
        return json.loads(content)


def _suggestion_from_payload(request: ReplyRequest, payload: dict[str, object]) -> ReplySuggestion:
    required = ("current_question", "suggested_reply", "translated_reply")
    if not all(isinstance(payload.get(key), str) and str(payload[key]).strip() for key in required):
        raise LLMError("AI 返回数据缺少必要字段")
    try:
        evidence = EvidenceStatus(str(payload.get("evidence_status", "not_found")))
    except ValueError:
        evidence = EvidenceStatus.NOT_FOUND
    suggested_reply = str(payload["suggested_reply"]).strip()
    translated_reply = str(payload["translated_reply"]).strip()
    if not request.citations and evidence is EvidenceStatus.DOCUMENTED:
        evidence = EvidenceStatus.NOT_FOUND
        suggested_reply = "资料中没有明确答案，请确认后再作答。"
        translated_reply = (
            "The documents do not contain a confirmed answer. Please verify before replying."
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
