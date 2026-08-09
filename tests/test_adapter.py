import sqlite3

import pytest

from yida_ai.adapters.captions.base import CaptionSource, CaptionSourceUnavailable
from yida_ai.adapters.captions.livecaptions_translator import LiveCaptionsTranslatorSource
from yida_ai.adapters.captions.mock import MockCaptionSource


def _make_upstream_db(path):
    with sqlite3.connect(path) as connection:
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


def test_livecaptions_missing_install_is_nonfatal(tmp_path):
    source = LiveCaptionsTranslatorSource(tmp_path / "missing.db")
    assert not source.status().available
    with pytest.raises(CaptionSourceUnavailable, match="未检测到"):
        source.poll()


def test_livecaptions_corrupt_database_is_reported(tmp_path):
    path = tmp_path / "broken.db"
    path.write_bytes(b"not a sqlite database")
    source = LiveCaptionsTranslatorSource(path, follow_new=False)
    with pytest.raises(CaptionSourceUnavailable, match="损坏|无效"):
        source.poll()
