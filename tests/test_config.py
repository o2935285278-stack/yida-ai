from itertools import permutations

import pytest

from yida_ai.config.languages import LANGUAGES, language_name
from yida_ai.config.scenes import SCENE_TEMPLATES
from yida_ai.config.settings import AppSettings, SettingsStore


def test_verified_languages_and_all_direction_pairs():
    expected = {"zh-CN", "en-US", "pt-BR"}
    assert expected <= set(LANGUAGES)
    for source, target in permutations(expected, 2):
        settings = AppSettings(source_language=source, user_language=target)
        settings.validate()
        assert language_name(source) != source


def test_all_required_scenes_are_configured():
    assert set(SCENE_TEMPLATES) == {
        "general",
        "business",
        "sales",
        "customer_service",
        "technical_support",
        "interview",
        "language_learning",
        "custom",
    }


def test_settings_round_trip_does_not_persist_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("YIDA_AI_API_KEY", "session-secret")
    store = SettingsStore(tmp_path / "config.json", tmp_path)
    settings = AppSettings(context_turns=7)
    store.save(settings)
    raw = store.path.read_text(encoding="utf-8")
    assert "session-secret" not in raw
    assert store.load().context_turns == 7


def test_corrupted_config_has_clear_error(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError, match="配置文件无法读取"):
        SettingsStore(path, tmp_path).load()


def test_legacy_adapter_config_migrates_to_caption_source(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"adapter":{"kind":"mock","poll_interval_ms":250}}', encoding="utf-8")
    settings = SettingsStore(path, tmp_path).load()
    assert settings.caption_source.kind == "mock"
    assert settings.caption_source.poll_interval_ms == 250

    SettingsStore(path, tmp_path).save(settings)
    saved = path.read_text(encoding="utf-8")
    assert '"caption_source"' in saved
    assert '"adapter"' not in saved
