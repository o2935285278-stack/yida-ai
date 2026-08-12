from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from yida_ai.core.models import CaptionEvent


class CaptionSourceError(RuntimeError):
    """Base error for caption sources."""


class CaptionSourceUnavailable(CaptionSourceError):
    """Raised when the configured caption source cannot be used."""


class CaptionActivityState(StrEnum):
    MISSING_DATABASE = "missing-database"
    DATABASE_READY = "database-ready"
    PROCESS_RUNNING = "process-running"
    WAITING_AUDIO = "waiting-audio"
    RECEIVING = "receiving"
    STALE = "stale"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class CaptionSourceStatus:
    available: bool
    source_name: str
    detail: str
    activity: CaptionActivityState = CaptionActivityState.DATABASE_READY
    database_readable: bool = False
    process_running: bool = False
    live: bool = False
    last_caption_at: datetime | None = None
    last_translation_at: datetime | None = None


class CaptionSource(ABC):
    """Uniform source of finalized caption and translation events."""

    @abstractmethod
    def status(self) -> CaptionSourceStatus:
        raise NotImplementedError

    @abstractmethod
    def poll(self, limit: int = 50) -> list[CaptionEvent]:
        raise NotImplementedError

    def redetect(self) -> CaptionSourceStatus:
        return self.status()

    def close(self) -> None:
        return None
