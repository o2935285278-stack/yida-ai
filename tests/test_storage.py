from datetime import UTC, datetime, timedelta

import pytest

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
    assert not path.exists()


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
