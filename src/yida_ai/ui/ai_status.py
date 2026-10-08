from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from yida_ai.config.settings import LLMSettings
from yida_ai.providers.llm.base import LLMErrorKind


class AIConnectionState(StrEnum):
    MOCK = "mock"
    UNCONFIGURED = "unconfigured"
    CONFIGURED_UNVERIFIED = "configured-unverified"
    TESTING = "testing"
    VERIFIED = "verified"
    INVALID_KEY = "invalid-key"
    MODEL_ERROR = "model-error"
    RATE_LIMITED = "rate-limited"
    QUOTA = "quota"
    TIMEOUT = "timeout"
    SERVER_ERROR = "server-error"
    NETWORK_ERROR = "network-error"


@dataclass(frozen=True, slots=True)
class AIConnectionStatus:
    state: AIConnectionState
    last_verified_at: str = ""
    provider: str = ""
    model: str = ""


def derive_ai_status(settings: LLMSettings, *, has_key: bool) -> AIConnectionStatus:
    if settings.provider == "mock":
        return AIConnectionStatus(AIConnectionState.MOCK, provider="Mock", model="Mock")
    configured = bool(settings.api_url.strip() and settings.model.strip() and has_key)
    if not configured:
        return AIConnectionStatus(
            AIConnectionState.UNCONFIGURED,
            provider=settings.provider,
            model=settings.model,
        )
    verified = bool(
        settings.last_verified_at
        and settings.last_verified_provider == settings.provider
        and settings.last_verified_model == settings.model
    )
    return AIConnectionStatus(
        AIConnectionState.VERIFIED if verified else AIConnectionState.CONFIGURED_UNVERIFIED,
        settings.last_verified_at if verified else "",
        settings.provider,
        settings.model,
    )


def state_from_error(kind: LLMErrorKind) -> AIConnectionState:
    return {
        LLMErrorKind.MISSING_KEY: AIConnectionState.UNCONFIGURED,
        LLMErrorKind.INVALID_KEY: AIConnectionState.INVALID_KEY,
        LLMErrorKind.MODEL_NOT_FOUND: AIConnectionState.MODEL_ERROR,
        LLMErrorKind.RATE_LIMITED: AIConnectionState.RATE_LIMITED,
        LLMErrorKind.QUOTA: AIConnectionState.QUOTA,
        LLMErrorKind.TIMEOUT: AIConnectionState.TIMEOUT,
        LLMErrorKind.SERVER_ERROR: AIConnectionState.SERVER_ERROR,
        LLMErrorKind.NETWORK: AIConnectionState.NETWORK_ERROR,
    }.get(kind, AIConnectionState.NETWORK_ERROR)
