from __future__ import annotations

import re
from pathlib import Path

from yida_ai.core.models import KnowledgeCitation
from yida_ai.retrieval.base import DocumentChunk, KnowledgeRetriever
from yida_ai.retrieval.documents import load_chunks


def tokenize(text: str) -> frozenset[str]:
    lowered = text.casefold()
    latin = re.findall(r"[a-zà-ÿ0-9][a-zà-ÿ0-9_-]+", lowered)
    cjk_runs = re.findall(r"[\u3400-\u9fff]+", lowered)
    cjk: list[str] = []
    for run in cjk_runs:
        if len(run) == 1:
            cjk.append(run)
        else:
            cjk.extend(run[index : index + 2] for index in range(len(run) - 1))
    return frozenset(latin + cjk)


class KeywordRetriever(KnowledgeRetriever):
    def __init__(self) -> None:
        self.chunks: list[tuple[DocumentChunk, frozenset[str]]] = []
        self.index_errors: list[str] = []

    def index_directory(self, directory: Path) -> int:
        indexed: list[tuple[DocumentChunk, frozenset[str]]] = []
        self.index_errors = []
        if directory.exists():
            for path in sorted(directory.iterdir()):
                if not path.is_file():
                    continue
                try:
                    chunks = load_chunks(path)
                except (OSError, RuntimeError) as exc:
                    self.index_errors.append(f"{path.name}: {exc}")
                    continue
                indexed.extend((chunk, tokenize(f"{path.name} {chunk.text}")) for chunk in chunks)
        self.chunks = indexed
        return len(indexed)

    def retrieve(self, query: str, limit: int = 3) -> tuple[KnowledgeCitation, ...]:
        query_tokens = tokenize(query)
        if not query_tokens or limit <= 0:
            return ()
        scored: list[tuple[float, DocumentChunk]] = []
        for chunk, chunk_tokens in self.chunks:
            overlap = query_tokens & chunk_tokens
            if not overlap:
                continue
            coverage = len(overlap) / len(query_tokens)
            specificity = sum(1.0 + min(len(token), 8) / 8 for token in overlap)
            score = round(specificity + coverage, 6)
            scored.append((score, chunk))
        scored.sort(key=lambda item: (-item[0], item[1].document_name, item[1].position))
        return tuple(
            KnowledgeCitation(
                document_id=chunk.document_id,
                document_name=chunk.document_name,
                excerpt=chunk.text,
                score=score,
                chunk_id=chunk.chunk_id,
            )
            for score, chunk in scored[:limit]
        )
