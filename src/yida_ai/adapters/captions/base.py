from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from yida_ai.core.models import CaptionEvent


class CaptionSourceError(RuntimeError):
    """Base error for caption sources."""


class CaptionSourceUnavailable(CaptionSourceError):
    """Raised when the configured caption source cannot be used."""


@dataclass(frozen=True, slots=True)
class CaptionSourceStatus:
    available: bool
    source_name: str
    detail: str


class CaptionSource(ABC):
    """Uniform source of finalized caption and translation events."""

    @abstractmethod
    def status(self) -> CaptionSourceStatus:
        raise NotImplementedError

    @abstractmethod
    def poll(self, limit: int = 50) -> list[CaptionEvent]:
        raise NotImplementedError

    def close(self) -> None:
        return None
