import threading
import time

import pytest

from yida_ai.adapters.captions.mock import MockCaptionSource
from yida_ai.adapters.captions.translated import TranslatedCaptionSource
from yida_ai.adapters.captions.windows_native import SnapshotSegments
from yida_ai.core.models import CaptionEvent
from yida_ai.retrieval.documents import KnowledgeLibrary


def test_rolling_caption_overlap_and_stable_repeat():
    segments = SnapshotSegments()
    assert segments.accept("Hello", 0) == ""
    assert segments.accept("Hello world.", .2) == ""
    assert segments.accept("Hello world.", .8) == "Hello world."
    assert segments.accept("Hello world.", 1.3) == ""
    assert segments.accept("world. How are you?", 1.4) == ""
    assert segments.accept("world. How are you?", 2) == "How are you?"


LANGUAGES = ("zh-CN", "en-US", "pt-BR")


@pytest.mark.parametrize("source,target", [
    (a, b) for a in LANGUAGES for b in LANGUAGES if a != b
])
def test_delayed_translation_updates_same_event(source, target):
    gate = threading.Event()
    class Translator:
        def translate_text(self, text, src, dst):
            assert (src, dst) == (source, target)
            gate.wait(2)
            return "translated"
    event = CaptionEvent(source_text="Question?", source_language=source,
                         translated_language=target)
    upstream = MockCaptionSource([event])
    adapter = TranslatedCaptionSource(upstream, Translator())
    try:
        first = adapter.poll()
        assert first[0].metadata["translation_pending"]
        assert first[0].event_id == event.event_id
        gate.set()
        deadline = time.monotonic() + 2
        updates = []
        while not updates and time.monotonic() < deadline:
            updates = adapter.poll()
            time.sleep(.01)
        assert len(updates) == 1
        assert updates[0].revision_of == event.event_id
        assert updates[0].translated_text == "translated"
    finally:
        gate.set()
        adapter.close()


def test_import_does_not_overwrite_same_name(tmp_path):
    library = KnowledgeLibrary(tmp_path / "knowledge")
    source = tmp_path / "notes.txt"
    source.write_text("first", encoding="utf-8")
    original = library.import_document(source)
    assert library.import_document(source) == original
    source.write_text("second", encoding="utf-8")
    second = library.import_document(source)
    assert second != original
    assert original.read_text(encoding="utf-8") == "first"
    assert second.read_text(encoding="utf-8") == "second"


def test_lct_delayed_writeback(tmp_path):
    import sqlite3

    from yida_ai.adapters.captions.livecaptions_translator import LiveCaptionsTranslatorSource
    db = tmp_path / "lct.db"
    with sqlite3.connect(db) as connection:
        connection.execute(
            "CREATE TABLE TranslationHistory (Id INTEGER PRIMARY KEY, SourceText TEXT,"
            " TranslatedText TEXT, Timestamp TEXT)"
        )
        connection.execute("INSERT INTO TranslationHistory VALUES (1, 'Hello?', '', '')")
    source = LiveCaptionsTranslatorSource(db, follow_new=False)
    assert len(source.poll()) == 1
    assert source.poll() == []
    with sqlite3.connect(db) as connection:
        connection.execute("UPDATE TranslationHistory SET TranslatedText='你好？' WHERE Id=1")
    updates = source.poll()
    assert len(updates) == 1
    assert updates[0].revision_of == "lct-1"
    assert source.poll() == []


def test_translation_failure_is_explicit():
    class Failing:
        def translate_text(self, *args):
            raise ValueError("offline")
    source = TranslatedCaptionSource(
        MockCaptionSource([CaptionEvent(source_text="test")]), Failing()
    )
    try:
        updates = source.poll()
        deadline = time.monotonic() + 2
        while not any(e.metadata.get("translation_error") for e in updates):
            assert time.monotonic() < deadline
            updates.extend(source.poll())
            time.sleep(.01)
        assert any(e.metadata.get("translation_error") == "offline" for e in updates)
    finally:
        source.close()
