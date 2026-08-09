from __future__ import annotations

from abc import ABC, abstractmethod


class TranslationProvider(ABC):
    @abstractmethod
    def translate(self, text: str, source_language: str, target_language: str) -> str:
        raise NotImplementedError


class PassthroughTranslationProvider(TranslationProvider):
    """Used when the caption adapter already supplied translated text."""

    def translate(self, text: str, source_language: str, target_language: str) -> str:
        return text
