from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum

from yida_ai.core.models import ReplyRequest, ReplySuggestion


class LLMErrorKind(StrEnum):
    CONFIGURATION = "configuration"
    MISSING_KEY = "missing-key"
    INVALID_KEY = "invalid-key"
    MODEL_NOT_FOUND = "model-not-found"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate-limited"
    QUOTA = "quota"
    SERVER_ERROR = "server-error"
    NETWORK = "network"
    INVALID_RESPONSE = "invalid-response"
    UNKNOWN = "unknown"


class LLMError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        kind: LLMErrorKind = LLMErrorKind.UNKNOWN,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.status_code = status_code


class LLMConfigurationError(LLMError):
    def __init__(self, message: str, *, kind: LLMErrorKind = LLMErrorKind.CONFIGURATION) -> None:
        super().__init__(message, kind=kind)


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, request: ReplyRequest) -> ReplySuggestion:
        raise NotImplementedError
