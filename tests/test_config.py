from itertools import permutations

import pytest

from yida_ai.config.languages import LANGUAGES, language_name, validate_language_code
from yida_ai.config.scenes import SCENE_TEMPLATES
from yida_ai.config.settings import AppSettings, SettingsStore


def test_verified_languages_and_all_direction_pairs():
    expected = {"zh-CN", "en-US", "pt-BR"}
    assert expected <= set(LANGUAGES)
    for source, target in permutations(expected, 2):
        settings = AppSettings(speech_language=source, translation_language=target)
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
        "brazilian_customer",
        "english_customer",
        "chinese_speaker",
        "chinese_to_brazilian",
    }


def test_customer_scene_language_presets_are_explicit():
    assert SCENE_TEMPLATES["brazilian_customer"].speech_language == "pt-BR"
    assert SCENE_TEMPLATES["english_customer"].speech_language == "en-US"
    assert SCENE_TEMPLATES["chinese_speaker"].speech_language == "zh-CN"


def test_settings_round_trip_does_not_persist_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("YIDA_AI_API_KEY", "session-secret")
    store = SettingsStore(tmp_path / "config.json", tmp_path)
    settings = AppSettings(context_turns=7)
    store.save(settings)
    raw = store.path.read_text(encoding="utf-8")
    assert "session-secret" not in raw
    assert store.load().context_turns == 7


def test_new_install_requires_onboarding_but_legacy_config_does_not(tmp_path):
    new_store = SettingsStore(tmp_path / "new.json", tmp_path / "new-data")
    new_settings = new_store.load()
    assert not new_settings.onboarding_completed
    assert not new_settings.privacy.save_history

    legacy_path = tmp_path / "legacy.json"
    legacy_path.write_text('{"speech_language":"en-US"}', encoding="utf-8")
    assert SettingsStore(legacy_path, tmp_path).load().onboarding_completed

    explicit_path = tmp_path / "explicit.json"
    explicit_path.write_text('{"onboarding_completed":false}', encoding="utf-8")
    assert not SettingsStore(explicit_path, tmp_path).load().onboarding_completed


def test_corrupted_config_has_clear_error(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError, match="配置文件无法读取"):
        SettingsStore(path, tmp_path).load()


def test_windows_utf8_bom_config_is_supported(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"context_turns":9}', encoding="utf-8-sig")
    assert SettingsStore(path, tmp_path).load().context_turns == 9


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


def test_legacy_language_fields_migrate_to_four_explicit_fields(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        '{"source_language":"en-US","user_language":"zh-CN",'
        '"reply_language":"en-US","ui_language":"pt-BR"}',
        encoding="utf-8",
    )
    store = SettingsStore(path, tmp_path)
    settings = store.load()
    assert settings.speech_language == "en-US"
    assert settings.translation_language == "zh-CN"
    assert settings.reply_language == "en-US"
    assert settings.interface_language == "pt-BR"
    store.save(settings)
    saved = path.read_text(encoding="utf-8")
    assert '"speech_language"' in saved
    assert '"translation_language"' in saved
    assert '"interface_language"' in saved
    assert '"source_language"' not in saved
    assert '"user_language"' not in saved
    assert '"ui_language"' not in saved


def test_custom_bcp47_language_codes_are_supported():
    assert validate_language_code("fr-FR") == "fr-FR"
    AppSettings(
        speech_language="fr-FR",
        translation_language="de-DE",
        reply_language="es-419",
    ).validate()
    with pytest.raises(ValueError, match="BCP-47"):
        AppSettings(speech_language="not a language").validate()
