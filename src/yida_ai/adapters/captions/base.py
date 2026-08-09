from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from yida_ai.core.models import CaptionEvent


class CaptionAdapterError(RuntimeError):
    """Base error for caption sources."""


class AdapterUnavailable(CaptionAdapterError):
    """Raised when the configured caption source cannot be used."""


@dataclass(frozen=True, slots=True)
class AdapterStatus:
    available: bool
    source_name: str
    detail: str


class CaptionAdapter(ABC):
    @abstractmethod
    def status(self) -> AdapterStatus:
        raise NotImplementedError

    @abstractmethod
    def poll(self, limit: int = 50) -> list[CaptionEvent]:
        raise NotImplementedError

    def close(self) -> None:
        return None
