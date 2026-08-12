from datetime import UTC, datetime, timedelta

import pytest

from yida_ai.application import build_runtime
from yida_ai.config.settings import (
    AppSettings,
    CaptionSourceSettings,
    PrivacySettings,
    SettingsStore,
)
from yida_ai.storage.history import HistoryStore, StorageError


def test_history_save_restore_clear_and_export(tmp_path, event_factory, suggestion_factory):
    store = HistoryStore(tmp_path / "history.db")
    event = event_factory()
    assert store.save("session-1", event, suggestion_factory())
    loaded = store.load_recent()
    assert loaded[0][0] == "session-1"
    assert loaded[0][1].source_text == event.source_text
    assert store.export_json(tmp_path / "out.json") == 1
    assert store.export_csv(tmp_path / "out.csv") == 1
    store.clear()
    assert store.load_recent() == []


def test_disabled_history_does_not_create_database(tmp_path, event_factory, suggestion_factory):
    path = tmp_path / "disabled.db"
    store = HistoryStore(path, enabled=False)
    assert not store.save("s", event_factory(), suggestion_factory())
    assert not store.save_event("s", event_factory())
    assert not path.exists()


def test_translation_only_event_round_trips_without_ai_suggestion(tmp_path, event_factory):
    store = HistoryStore(tmp_path / "history.db")
    event = event_factory()
    assert store.save_event("translation-session", event)
    loaded = store.load_recent()
    assert loaded[0][1].source_text == event.source_text
    assert loaded[0][2] is None


def test_runtime_restores_only_configured_recent_history(
    tmp_path, event_factory, suggestion_factory
):
    settings_store = SettingsStore(tmp_path / "config.json", tmp_path)
    settings_store.save(
        AppSettings(
            context_turns=15,
            caption_source=CaptionSourceSettings(kind="mock"),
            privacy=PrivacySettings(retention_days=0),
        )
    )
    history = HistoryStore(tmp_path / "history.db")
    for index in range(20):
        event = event_factory(f"event-{index}", f"Question {index}?")
        history.save("old-session", event, suggestion_factory(event_id=event.event_id))

    runtime = build_runtime(settings_store)
    try:
        assert len(runtime.restored_history) == 15
        assert len(runtime.controller.engine.conversation.events) == 15
        assert runtime.controller.engine.conversation.events[0].event_id == "event-5"
        assert runtime.controller.engine.conversation.events[-1].event_id == "event-19"
    finally:
        runtime.close()


def test_retention_prunes_old_rows(tmp_path, event_factory, suggestion_factory):
    store = HistoryStore(tmp_path / "history.db", retention_days=5)
    event = event_factory()
    store.save("s", event, suggestion_factory())
    assert store.prune(now=datetime.now(UTC) + timedelta(days=365)) == 1


def test_corrupt_history_database_is_reported(tmp_path):
    path = tmp_path / "broken.db"
    path.write_bytes(b"not sqlite")
    with pytest.raises(StorageError, match="损坏"):
        HistoryStore(path)
