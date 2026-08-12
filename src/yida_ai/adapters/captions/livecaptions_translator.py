from __future__ import annotations

import os
import sqlite3
from collections.abc import Callable
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from yida_ai.adapters.captions.base import (
    CaptionActivityState,
    CaptionSource,
    CaptionSourceStatus,
    CaptionSourceUnavailable,
)
from yida_ai.core.models import CaptionEvent


def common_database_candidates(
    bundled_lct_directory: Path | None = None,
    *,
    running_lct_directory: Path | None = None,
    include_external_candidates: bool = True,
) -> tuple[Path, ...]:
    candidates: list[Path] = []
    configured = os.getenv("LIVECAPTIONS_TRANSLATOR_DB", "").strip()
    if configured:
        candidates.append(Path(configured).expanduser())
    if running_lct_directory is not None:
        candidates.append(running_lct_directory / "translation_history.db")
    if bundled_lct_directory is not None:
        candidates.append(bundled_lct_directory / "translation_history.db")
    if include_external_candidates:
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


def database_candidates(
    explicit: str | Path | None = None,
    bundled_lct_directory: Path | None = None,
    *,
    running_lct_directory: Path | None = None,
    include_external_candidates: bool = True,
) -> tuple[Path, ...]:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    candidates.extend(
        common_database_candidates(
            bundled_lct_directory,
            running_lct_directory=running_lct_directory,
            include_external_candidates=include_external_candidates,
        )
    )
    unique: list[Path] = []
    for item in candidates:
        if item not in unique:
            unique.append(item)
    return tuple(unique)


def detect_database_path(
    explicit: str | Path | None = None,
    bundled_lct_directory: Path | None = None,
    *,
    running_lct_directory: Path | None = None,
    include_external_candidates: bool = True,
) -> Path | None:
    return next(
        (
            path
            for path in database_candidates(
                explicit,
                bundled_lct_directory,
                running_lct_directory=running_lct_directory,
                include_external_candidates=include_external_candidates,
            )
            if path.is_file()
        ),
        None,
    )


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
        bundled_lct_directory: Path | None = None,
        running_lct_directory: Path | None = None,
        include_external_candidates: bool = True,
        process_running_probe: Callable[[], bool] | None = None,
        stale_after_seconds: float = 30.0,
    ) -> None:
        self._explicit_database_path = database_path
        self._bundled_lct_directory = bundled_lct_directory
        self._running_lct_directory = running_lct_directory
        self._follow_new = follow_new
        self._include_external_candidates = include_external_candidates
        self._process_running_probe = process_running_probe or _is_lct_running
        self.stale_after_seconds = stale_after_seconds
        self.database_path = detect_database_path(
            database_path,
            bundled_lct_directory,
            running_lct_directory=running_lct_directory,
            include_external_candidates=include_external_candidates,
        )
        self.source_language = source_language
        self.translated_language = translated_language
        self.last_row_id = 0
        self._columns: dict[str, str] | None = None
        self.last_caption_at: datetime | None = None
        self.last_translation_at: datetime | None = None
        if self.database_path and follow_new:
            self.last_row_id = self._max_id()

    def status(self) -> CaptionSourceStatus:
        self._ensure_database_path()
        process_running = self._process_running_probe()
        if self.database_path is None:
            return CaptionSourceStatus(
                False,
                "LiveCaptions Translator",
                (
                    "LCT 正在运行，等待生成字幕数据库"
                    if process_running
                    else "字幕数据库不存在；请启动 LCT 并完成配置"
                ),
                (
                    CaptionActivityState.PROCESS_RUNNING
                    if process_running
                    else CaptionActivityState.MISSING_DATABASE
                ),
                False,
                process_running,
            )
        try:
            columns = self._resolve_columns()
            self._read_latest_activity(columns)
        except CaptionSourceUnavailable as exc:
            return CaptionSourceStatus(
                False,
                "LiveCaptions Translator",
                str(exc),
                CaptionActivityState.ERROR,
                False,
                process_running,
            )
        modified_at = datetime.fromtimestamp(self.database_path.stat().st_mtime, tz=UTC)
        age = max(0.0, (datetime.now(UTC) - modified_at).total_seconds())
        if not process_running:
            activity = CaptionActivityState.DATABASE_READY
            detail = "字幕数据库可读，但 LCT 进程未运行"
            live = False
        elif self.last_caption_at is None:
            activity = CaptionActivityState.WAITING_AUDIO
            detail = "LCT 正在运行，等待语音"
            live = False
        elif age <= self.stale_after_seconds:
            activity = CaptionActivityState.RECEIVING
            detail = "正在接收实时字幕"
            live = True
        else:
            activity = CaptionActivityState.STALE
            detail = "字幕数据库可读，但数据已长时间没有更新"
            live = False
        return CaptionSourceStatus(
            True,
            "LiveCaptions Translator",
            detail,
            activity,
            True,
            process_running,
            live,
            self.last_caption_at,
            self.last_translation_at,
        )

    def poll(self, limit: int = 50) -> list[CaptionEvent]:
        self._ensure_database_path()
        if self.database_path is None:
            raise CaptionSourceUnavailable(
                "正在等待 LiveCaptions Translator 生成字幕数据库；无需重启译答 AI。"
            )
        columns = self._resolve_columns()
        query = (
            f'SELECT "{columns["id"]}", "{columns["source"]}", '
            f'"{columns["translated"]}", "{columns.get("timestamp", columns["id"])}" '
            f'FROM "{columns["table"]}" WHERE "{columns["id"]}" > ? '
            f'ORDER BY "{columns["id"]}" ASC LIMIT ?'
        )
        try:
            with closing(self._connect_readonly()) as connection:
                rows = connection.execute(query, (self.last_row_id, limit)).fetchall()
        except sqlite3.Error as exc:
            raise CaptionSourceUnavailable(f"字幕数据库无法读取：{exc}") from exc
        events: list[CaptionEvent] = []
        for row_id, source, translated, timestamp in rows:
            self.last_row_id = max(self.last_row_id, int(row_id))
            source_text = str(source or "").strip()
            translated_text, translation_error = _sanitize_translation(str(translated or ""))
            if not source_text:
                continue
            metadata: dict[str, object] = {"upstream_row_id": int(row_id)}
            if translation_error:
                metadata["translation_error"] = translation_error
            occurred_at = _parse_timestamp(timestamp)
            self.last_caption_at = occurred_at
            if translated_text:
                self.last_translation_at = occurred_at
            events.append(
                CaptionEvent(
                    event_id=f"lct-{row_id}",
                    source_text=source_text,
                    translated_text=translated_text,
                    source_language=self.source_language,
                    translated_language=self.translated_language,
                    source="livecaptions-translator",
                    occurred_at=occurred_at,
                    is_final=True,
                    metadata=metadata,
                )
            )
        return events

    def redetect(self) -> CaptionSourceStatus:
        self.database_path = None
        self._columns = None
        self.last_row_id = 0
        self._ensure_database_path()
        return self.status()

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
            with closing(self._connect_readonly()) as connection:
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
            with closing(self._connect_readonly()) as connection:
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

    def _read_latest_activity(self, columns: dict[str, str]) -> None:
        query = (
            f'SELECT "{columns["translated"]}", '
            f'"{columns.get("timestamp", columns["id"])}" '
            f'FROM "{columns["table"]}" ORDER BY "{columns["id"]}" DESC LIMIT 1'
        )
        try:
            with closing(self._connect_readonly()) as connection:
                row = connection.execute(query).fetchone()
        except sqlite3.Error as exc:
            raise CaptionSourceUnavailable(f"字幕数据库无法读取：{exc}") from exc
        if row is None:
            self.last_caption_at = None
            self.last_translation_at = None
            return
        translated, timestamp = row
        occurred_at = _parse_timestamp(timestamp)
        self.last_caption_at = occurred_at
        cleaned, _error = _sanitize_translation(str(translated or ""))
        self.last_translation_at = occurred_at if cleaned else None

    def _ensure_database_path(self) -> None:
        detected = detect_database_path(
            self._explicit_database_path,
            self._bundled_lct_directory,
            running_lct_directory=self._running_lct_directory,
            include_external_candidates=self._include_external_candidates,
        )
        if detected == self.database_path and (detected is None or self.database_path.is_file()):
            return
        self.database_path = detected
        self._columns = None
        self.last_row_id = 0
        if detected is not None and self._follow_new:
            self.last_row_id = self._max_id()


def _first(mapping: dict[str, str], *keys: str) -> str | None:
    return next((mapping[key] for key in keys if key in mapping), None)


def _is_lct_running() -> bool:
    from yida_ai.components.livecaptions_translator import find_running_lct_processes

    return bool(find_running_lct_processes())


def _strip_latency(value: str) -> str:
    value = value.strip()
    if value.startswith("[") and "]" in value[:24]:
        return value.split("]", 1)[1].strip()
    return value


def _sanitize_translation(value: str) -> tuple[str, str]:
    translated = _strip_latency(value)
    folded = translated.casefold()
    failure_markers = (
        "translation failed",
        "request was canceled",
        "request was cancelled",
        "timed out",
        "timeout",
        "[error]",
        "[warning]",
    )
    if any(marker in folded for marker in failure_markers):
        return "", translated[:240]
    return translated, ""


def _parse_timestamp(value: object) -> datetime:
    try:
        return datetime.fromtimestamp(float(value), tz=UTC)
    except (TypeError, ValueError, OSError):
        return datetime.now(UTC)
