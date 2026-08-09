from __future__ import annotations

import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from yida_ai.adapters.captions.base import (
    CaptionSource,
    CaptionSourceStatus,
    CaptionSourceUnavailable,
)
from yida_ai.core.models import CaptionEvent


def common_database_candidates() -> tuple[Path, ...]:
    candidates: list[Path] = []
    configured = os.getenv("LIVECAPTIONS_TRANSLATOR_DB", "").strip()
    if configured:
        candidates.append(Path(configured).expanduser())
    home = Path.home()
    candidates.append(home / "Apps" / "LiveCaptions Translator" / "translation_history.db")
    for variable in ("LOCALAPPDATA", "APPDATA"):
        value = os.getenv(variable)
        if value:
            root = Path(value)
            candidates.extend(
                (
                    root / "LiveCaptions Translator" / "translation_history.db",
                    root / "LiveCaptions-Translator" / "translation_history.db",
                )
            )
    unique: list[Path] = []
    for item in candidates:
        if item not in unique:
            unique.append(item)
    return tuple(unique)


def detect_database_path(explicit: str | Path | None = None) -> Path | None:
    if explicit:
        candidate = Path(explicit).expanduser()
        return candidate if candidate.is_file() else None
    return next((path for path in common_database_candidates() if path.is_file()), None)


class LiveCaptionsTranslatorSource(CaptionSource):
    """Read translated caption rows behind a stable CaptionEvent interface.

    All knowledge of the upstream SQLite schema is intentionally confined here.
    The source never reads the upstream API configuration and never terminates
    or starts the upstream process.
    """

    def __init__(
        self,
        database_path: str | Path | None = None,
        *,
        source_language: str = "auto",
        translated_language: str = "",
        follow_new: bool = True,
    ) -> None:
        self.database_path = detect_database_path(database_path)
        self.source_language = source_language
        self.translated_language = translated_language
        self.last_row_id = 0
        self._columns: dict[str, str] | None = None
        if self.database_path and follow_new:
            self.last_row_id = self._max_id()

    def status(self) -> CaptionSourceStatus:
        if self.database_path is None:
            return CaptionSourceStatus(
                False,
                "LiveCaptions Translator",
                "未找到 translation_history.db。请在设置中选择数据库文件。",
            )
        try:
            self._resolve_columns()
        except CaptionSourceUnavailable as exc:
            return CaptionSourceStatus(False, "LiveCaptions Translator", str(exc))
        return CaptionSourceStatus(True, "LiveCaptions Translator", str(self.database_path))

    def poll(self, limit: int = 50) -> list[CaptionEvent]:
        if self.database_path is None:
            raise CaptionSourceUnavailable(
                "未检测到 LiveCaptions Translator 数据库；可切换到模拟字幕模式进行演示。"
            )
        columns = self._resolve_columns()
        query = (
            f'SELECT "{columns["id"]}", "{columns["source"]}", '
            f'"{columns["translated"]}", "{columns.get("timestamp", columns["id"])}" '
            f'FROM "{columns["table"]}" WHERE "{columns["id"]}" > ? '
            f'ORDER BY "{columns["id"]}" ASC LIMIT ?'
        )
        try:
            with self._connect_readonly() as connection:
                rows = connection.execute(query, (self.last_row_id, limit)).fetchall()
        except sqlite3.Error as exc:
            raise CaptionSourceUnavailable(f"字幕数据库无法读取：{exc}") from exc
        events: list[CaptionEvent] = []
        for row_id, source, translated, timestamp in rows:
            self.last_row_id = max(self.last_row_id, int(row_id))
            source_text = str(source or "").strip()
            translated_text = _strip_latency(str(translated or ""))
            if not source_text or not translated_text:
                continue
            if "[ERROR]" in translated_text or "[WARNING]" in translated_text:
                continue
            events.append(
                CaptionEvent(
                    event_id=f"lct-{row_id}",
                    source_text=source_text,
                    translated_text=translated_text,
                    source_language=self.source_language,
                    translated_language=self.translated_language,
                    source="livecaptions-translator",
                    occurred_at=_parse_timestamp(timestamp),
                    is_final=True,
                    metadata={"upstream_row_id": int(row_id)},
                )
            )
        return events

    def _connect_readonly(self) -> sqlite3.Connection:
        assert self.database_path is not None
        try:
            uri = self.database_path.resolve().as_uri() + "?mode=ro"
            return sqlite3.connect(uri, uri=True, timeout=0.4)
        except (OSError, sqlite3.Error) as exc:
            raise CaptionSourceUnavailable(f"无法打开字幕数据库：{exc}") from exc

    def _max_id(self) -> int:
        try:
            columns = self._resolve_columns()
            with self._connect_readonly() as connection:
                row = connection.execute(
                    f'SELECT COALESCE(MAX("{columns["id"]}"), 0) FROM "{columns["table"]}"'
                ).fetchone()
            return int(row[0])
        except CaptionSourceUnavailable:
            return 0

    def _resolve_columns(self) -> dict[str, str]:
        if self._columns is not None:
            return self._columns
        if self.database_path is None:
            raise CaptionSourceUnavailable("LiveCaptions Translator 数据库路径尚未配置")
        try:
            with self._connect_readonly() as connection:
                tables = [
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                ]
                for table in tables:
                    names = [row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')]
                    lowered = {name.lower(): name for name in names}
                    identifier = _first(lowered, "id", "rowid")
                    source = _first(lowered, "sourcetext", "source_text", "originaltext")
                    translated = _first(lowered, "translatedtext", "translated_text", "translation")
                    if identifier and source and translated:
                        self._columns = {
                            "table": table,
                            "id": identifier,
                            "source": source,
                            "translated": translated,
                        }
                        timestamp = _first(lowered, "timestamp", "createdat", "created_at")
                        if timestamp:
                            self._columns["timestamp"] = timestamp
                        return self._columns
        except sqlite3.DatabaseError as exc:
            raise CaptionSourceUnavailable(f"字幕数据库已损坏或格式无效：{exc}") from exc
        raise CaptionSourceUnavailable("数据库中没有可识别的字幕历史表")


def _first(mapping: dict[str, str], *keys: str) -> str | None:
    return next((mapping[key] for key in keys if key in mapping), None)


def _strip_latency(value: str) -> str:
    value = value.strip()
    if value.startswith("[") and "]" in value[:24]:
        return value.split("]", 1)[1].strip()
    return value


def _parse_timestamp(value: object) -> datetime:
    try:
        return datetime.fromtimestamp(float(value), tz=UTC)
    except (TypeError, ValueError, OSError):
        return datetime.now(UTC)
