import sqlite3

import pytest

from yida_ai.adapters.captions.base import AdapterUnavailable
from yida_ai.adapters.captions.livecaptions_translator import LiveCaptionsTranslatorAdapter


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


def test_livecaptions_adapter_reads_stable_caption_event(tmp_path):
    path = tmp_path / "translation_history.db"
    _make_upstream_db(path)
    adapter = LiveCaptionsTranslatorAdapter(
        path, source_language="pt-BR", translated_language="zh-CN", follow_new=False
    )
    event = adapter.poll()[0]
    assert event.source_text == "Bom dia"
    assert event.translated_text == "早上好"
    assert event.source == "livecaptions-translator"
    assert event.metadata == {"upstream_row_id": 1}


def test_livecaptions_missing_install_is_nonfatal(tmp_path):
    adapter = LiveCaptionsTranslatorAdapter(tmp_path / "missing.db")
    assert not adapter.status().available
    with pytest.raises(AdapterUnavailable, match="未检测到"):
        adapter.poll()


def test_livecaptions_corrupt_database_is_reported(tmp_path):
    path = tmp_path / "broken.db"
    path.write_bytes(b"not a sqlite database")
    adapter = LiveCaptionsTranslatorAdapter(path, follow_new=False)
    with pytest.raises(AdapterUnavailable, match="损坏|无效"):
        adapter.poll()
