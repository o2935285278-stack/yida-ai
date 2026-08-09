from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from yida_ai.core.models import KnowledgeCitation


class KnowledgeError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    document_id: str
    document_name: str
    chunk_id: str
    text: str
    position: int


class KnowledgeRetriever(ABC):
    @abstractmethod
    def index_directory(self, directory: Path) -> int:
        raise NotImplementedError

    @abstractmethod
    def retrieve(self, query: str, limit: int = 3) -> tuple[KnowledgeCitation, ...]:
        raise NotImplementedError
