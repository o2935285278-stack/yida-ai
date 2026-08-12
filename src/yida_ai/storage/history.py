from __future__ import annotations

import csv
import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

from yida_ai.core.models import (
    CaptionEvent,
    EvidenceStatus,
    KnowledgeCitation,
    ReplySuggestion,
)


class StorageError(RuntimeError):
    pass


class HistoryStore:
    def __init__(self, path: Path, *, enabled: bool = True, retention_days: int = 30) -> None:
        self.path = path
        self.enabled = enabled
        self.retention_days = retention_days
        if enabled:
            self._initialize()

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            connection = sqlite3.connect(self.path, timeout=2)
            connection.row_factory = sqlite3.Row
            return connection
        except sqlite3.Error as exc:
            raise StorageError(f"无法打开历史数据库：{exc}") from exc

    def _initialize(self) -> None:
        try:
            with closing(self._connect()) as connection, connection:
                connection.execute(
                    """
                        CREATE TABLE IF NOT EXISTS turns (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            session_id TEXT NOT NULL,
                            event_id TEXT NOT NULL UNIQUE,
                            occurred_at TEXT NOT NULL,
                            source_name TEXT NOT NULL,
                            source_language TEXT NOT NULL,
                            translated_language TEXT NOT NULL,
                            source_text TEXT NOT NULL,
                            translated_text TEXT NOT NULL,
                            current_question TEXT NOT NULL,
                            suggested_reply TEXT NOT NULL,
                            translated_reply TEXT NOT NULL,
                            evidence_status TEXT NOT NULL,
                            citations_json TEXT NOT NULL
                        )
                        """
                )
                result = connection.execute("PRAGMA integrity_check").fetchone()[0]
                if result != "ok":
                    raise StorageError(f"历史数据库完整性检查失败：{result}")
        except sqlite3.DatabaseError as exc:
            raise StorageError(f"历史数据库已损坏：{exc}") from exc

    def save(self, session_id: str, event: CaptionEvent, suggestion: ReplySuggestion) -> bool:
        if not self.enabled:
            return False
        citations = [
            {
                "document_id": item.document_id,
                "document_name": item.document_name,
                "excerpt": item.excerpt,
                "score": item.score,
                "chunk_id": item.chunk_id,
            }
            for item in suggestion.citations
        ]
        try:
            with closing(self._connect()) as connection, connection:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO turns (
                        session_id, event_id, occurred_at, source_name,
                        source_language, translated_language, source_text,
                        translated_text, current_question, suggested_reply,
                        translated_reply, evidence_status, citations_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        event.event_id,
                        event.occurred_at.isoformat(),
                        event.source,
                        event.source_language,
                        event.translated_language,
                        event.source_text,
                        event.translated_text,
                        suggestion.current_question,
                        suggestion.suggested_reply,
                        suggestion.translated_reply,
                        suggestion.evidence_status.value,
                        json.dumps(citations, ensure_ascii=False),
                    ),
                )
        except sqlite3.Error as exc:
            raise StorageError(f"保存历史失败：{exc}") from exc
        return True

    def save_event(self, session_id: str, event: CaptionEvent) -> bool:
        """Persist a caption immediately, even when AI is disabled or still running."""
        suggestion = ReplySuggestion(
            request_id=f"pending-{event.event_id}",
            event_id=event.event_id,
            current_question="",
            suggested_reply="",
            translated_reply="",
            evidence_status=EvidenceStatus.NOT_FOUND,
        )
        return self.save(session_id, event, suggestion)

    def load_recent(
        self, limit: int = 15
    ) -> list[tuple[str, CaptionEvent, ReplySuggestion | None]]:
        if not self.enabled or not self.path.exists():
            return []
        try:
            with closing(self._connect()) as connection:
                rows = connection.execute(
                    "SELECT * FROM turns ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError(f"读取历史失败：{exc}") from exc
        result: list[tuple[str, CaptionEvent, ReplySuggestion | None]] = []
        for row in reversed(rows):
            event = CaptionEvent(
                event_id=row["event_id"],
                occurred_at=datetime.fromisoformat(row["occurred_at"]),
                source=row["source_name"],
                source_language=row["source_language"],
                translated_language=row["translated_language"],
                source_text=row["source_text"],
                translated_text=row["translated_text"],
            )
            citations = tuple(
                KnowledgeCitation(**item) for item in json.loads(row["citations_json"])
            )
            suggestion = None
            if row["current_question"] or row["suggested_reply"] or row["translated_reply"]:
                suggestion = ReplySuggestion(
                    request_id=f"history-{row['id']}",
                    event_id=event.event_id,
                    current_question=row["current_question"],
                    suggested_reply=row["suggested_reply"],
                    translated_reply=row["translated_reply"],
                    evidence_status=EvidenceStatus(row["evidence_status"]),
                    citations=citations,
                )
            result.append((row["session_id"], event, suggestion))
        return result

    def clear(self) -> None:
        if not self.path.exists():
            return
        try:
            with closing(self._connect()) as connection, connection:
                connection.execute("DELETE FROM turns")
        except sqlite3.Error as exc:
            raise StorageError(f"清空历史失败：{exc}") from exc

    def prune(self, now: datetime | None = None) -> int:
        if not self.enabled or self.retention_days <= 0 or not self.path.exists():
            return 0
        cutoff = (now or datetime.now(UTC)) - timedelta(days=self.retention_days)
        try:
            with closing(self._connect()) as connection, connection:
                cursor = connection.execute(
                    "DELETE FROM turns WHERE occurred_at < ?", (cutoff.isoformat(),)
                )
                return cursor.rowcount
        except sqlite3.Error as exc:
            raise StorageError(f"清理过期历史失败：{exc}") from exc

    def export_json(self, path: Path) -> int:
        records = self._all_rows()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps([dict(row) for row in records], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return len(records)

    def export_csv(self, path: Path) -> int:
        records = self._all_rows()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            if not records:
                return 0
            writer = csv.DictWriter(handle, fieldnames=records[0].keys())
            writer.writeheader()
            writer.writerows(dict(row) for row in records)
        return len(records)

    def _all_rows(self) -> list[sqlite3.Row]:
        if not self.path.exists():
            return []
        try:
            with closing(self._connect()) as connection:
                return connection.execute("SELECT * FROM turns ORDER BY id ASC").fetchall()
        except sqlite3.Error as exc:
            raise StorageError(f"导出历史失败：{exc}") from exc
