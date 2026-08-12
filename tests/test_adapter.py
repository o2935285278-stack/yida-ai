import sqlite3
from contextlib import closing

import pytest

from yida_ai.adapters.captions.base import (
    CaptionActivityState,
    CaptionSource,
    CaptionSourceUnavailable,
)
from yida_ai.adapters.captions.livecaptions_translator import LiveCaptionsTranslatorSource
from yida_ai.adapters.captions.mock import MockCaptionSource


def _make_upstream_db(path):
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute(
            "CREATE TABLE translations (Id INTEGER PRIMARY KEY, SourceText TEXT, "
            "TranslatedText TEXT, Timestamp REAL)"
        )
        connection.execute(
            "INSERT INTO translations VALUES (1, ?, ?, ?)",
            ("Bom dia", "[120ms] 早上好", 1_700_000_000),
        )


def test_caption_source_contract_has_both_implementations():
    assert issubclass(LiveCaptionsTranslatorSource, CaptionSource)
    assert issubclass(MockCaptionSource, CaptionSource)


def test_livecaptions_source_reads_stable_caption_event(tmp_path):
    path = tmp_path / "translation_history.db"
    _make_upstream_db(path)
    source = LiveCaptionsTranslatorSource(
        path, source_language="pt-BR", translated_language="zh-CN", follow_new=False
    )
    event = source.poll()[0]
    assert event.source_text == "Bom dia"
    assert event.translated_text == "早上好"
    assert event.source == "livecaptions-translator"
    assert event.metadata == {"upstream_row_id": 1}


def test_old_database_is_not_reported_as_live_input(tmp_path):
    path = tmp_path / "translation_history.db"
    _make_upstream_db(path)
    source = LiveCaptionsTranslatorSource(
        path,
        follow_new=False,
        process_running_probe=lambda: False,
    )
    status = source.status()
    assert status.activity is CaptionActivityState.DATABASE_READY
    assert status.database_readable
    assert not status.process_running
    assert not status.live
    assert status.last_caption_at is not None


def test_recent_database_with_running_lct_reports_receiving(tmp_path):
    path = tmp_path / "translation_history.db"
    _make_upstream_db(path)
    source = LiveCaptionsTranslatorSource(
        path,
        follow_new=False,
        process_running_probe=lambda: True,
        stale_after_seconds=60,
    )
    status = source.status()
    assert status.activity is CaptionActivityState.RECEIVING
    assert status.live
    assert status.last_translation_at is not None


def test_livecaptions_source_keeps_source_when_upstream_translation_fails(tmp_path):
    path = tmp_path / "translation_history.db"
    _make_upstream_db(path)
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute(
            "INSERT INTO translations VALUES (2, ?, ?, ?)",
            (
                "Pode explicar novamente?",
                "Translation Failed: request was canceled due to timeout (> 8 seconds)",
                1_700_000_001,
            ),
        )
        connection.execute(
            "INSERT INTO translations VALUES (3, ?, ?, ?)",
            ("E o preço?", "", 1_700_000_002),
        )
    source = LiveCaptionsTranslatorSource(path, follow_new=False)
    events = source.poll()
    assert [event.source_text for event in events] == [
        "Bom dia",
        "Pode explicar novamente?",
        "E o preço?",
    ]
    assert events[1].translated_text == ""
    assert "translation_error" in events[1].metadata
    assert events[2].translated_text == ""


def test_livecaptions_missing_install_is_nonfatal(tmp_path):
    source = LiveCaptionsTranslatorSource(
        tmp_path / "missing.db",
        include_external_candidates=False,
    )
    assert not source.status().available
    with pytest.raises(CaptionSourceUnavailable, match="等待.*数据库"):
        source.poll()


def test_livecaptions_dynamically_discovers_later_database(tmp_path):
    bundled = tmp_path / "components" / "LiveCaptionsTranslator"
    bundled.mkdir(parents=True)
    source = LiveCaptionsTranslatorSource(
        bundled_lct_directory=bundled,
        follow_new=False,
        include_external_candidates=False,
    )
    assert not source.status().available
    _make_upstream_db(bundled / "translation_history.db")
    assert source.status().available
    assert source.poll()[0].source_text == "Bom dia"


def test_database_detection_prefers_explicit_then_environment(tmp_path, monkeypatch):
    explicit = tmp_path / "manual.db"
    environment = tmp_path / "environment.db"
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    _make_upstream_db(explicit)
    _make_upstream_db(environment)
    _make_upstream_db(bundled / "translation_history.db")
    monkeypatch.setenv("LIVECAPTIONS_TRANSLATOR_DB", str(environment))
    source = LiveCaptionsTranslatorSource(
        explicit,
        bundled_lct_directory=bundled,
        follow_new=False,
        include_external_candidates=False,
    )
    assert source.database_path == explicit


def test_running_lct_database_is_preferred_over_bundled_database(tmp_path):
    running = tmp_path / "running"
    bundled = tmp_path / "bundled"
    running.mkdir()
    bundled.mkdir()
    _make_upstream_db(running / "translation_history.db")
    _make_upstream_db(bundled / "translation_history.db")
    source = LiveCaptionsTranslatorSource(
        bundled_lct_directory=bundled,
        running_lct_directory=running,
        follow_new=False,
        include_external_candidates=False,
    )
    assert source.database_path == running / "translation_history.db"


def test_higher_priority_database_can_appear_later(tmp_path, monkeypatch):
    explicit = tmp_path / "manual.db"
    environment = tmp_path / "environment.db"
    _make_upstream_db(environment)
    monkeypatch.setenv("LIVECAPTIONS_TRANSLATOR_DB", str(environment))
    source = LiveCaptionsTranslatorSource(
        explicit,
        follow_new=False,
        include_external_candidates=False,
    )
    assert source.database_path == environment
    _make_upstream_db(explicit)
    assert source.status().available
    assert source.database_path == explicit


def test_livecaptions_corrupt_database_is_reported(tmp_path):
    path = tmp_path / "broken.db"
    path.write_bytes(b"not a sqlite database")
    source = LiveCaptionsTranslatorSource(path, follow_new=False)
    with pytest.raises(CaptionSourceUnavailable, match="损坏|无效"):
        source.poll()
