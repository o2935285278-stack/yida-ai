from __future__ import annotations

from abc import ABC, abstractmethod

from yida_ai.core.models import ReplyRequest, ReplySuggestion


class LLMError(RuntimeError):
    pass


class LLMConfigurationError(LLMError):
    pass


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, request: ReplyRequest) -> ReplySuggestion:
        raise NotImplementedError
