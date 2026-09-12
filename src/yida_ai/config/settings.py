from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from yida_ai.config.languages import validate_language_code, validate_language_direction
from yida_ai.security import SecretStore, SecretStoreError


def default_data_dir() -> Path:
    configured = os.getenv("YIDA_AI_DATA_DIR")
    if configured:
        return Path(configured).expanduser()
    base = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return base / "YidaAI"


@dataclass(slots=True)
class LLMSettings:
    provider: str = "mock"
    api_url: str = ""
    model: str = ""
    timeout_seconds: float = 12.0
    max_tokens: int = 600
    temperature: float = 0.2
    retry_limit: int = 1
    last_verified_at: str = ""
    last_verified_provider: str = ""
    last_verified_model: str = ""

    @property
    def api_key(self) -> str:
        return os.getenv("YIDA_AI_API_KEY", "").strip()


@dataclass(slots=True)
class CaptionSourceSettings:
    kind: str = "windows-captions"
    database_path: str = ""
    poll_interval_ms: int = 180
    auto_start_windows_captions: bool = True
    show_system_caption_window: bool = True


@dataclass(slots=True)
class PrivacySettings:
    save_history: bool = False
    retention_days: int = 30


@dataclass(slots=True)
class AppSettings:
    onboarding_completed: bool = False
    speech_language: str = "pt-BR"
    translation_language: str = "zh-CN"
    reply_language: str = "pt-BR"
    scene: str = "general"
    custom_scene_instruction: str = ""
    reply_mode: str = "every"
    reply_length: str = "short"
    context_turns: int = 15
    interface_language: str = "zh-CN"
    llm: LLMSettings = field(default_factory=LLMSettings)
    caption_source: CaptionSourceSettings = field(default_factory=CaptionSourceSettings)
    privacy: PrivacySettings = field(default_factory=PrivacySettings)

    def validate(self) -> None:
        validate_language_code(self.speech_language)
        validate_language_code(self.translation_language)
        validate_language_code(self.reply_language)
        validate_language_direction(self.speech_language, self.translation_language)
        if not 1 <= self.context_turns <= 50:
            raise ValueError("最近对话轮数必须在 1 到 50 之间")
        if not 0 <= self.privacy.retention_days <= 3650:
            raise ValueError("数据保留期限必须在 0 到 3650 天之间")
        if self.reply_mode not in {"translation", "auto", "every", "confirm"}:
            raise ValueError("未知回复模式")
        if self.reply_length not in {"short", "medium", "detailed"}:
            raise ValueError("未知回复长度")
        if self.interface_language not in {"zh-CN", "en-US", "pt-BR"}:
            raise ValueError("界面语言必须是 zh-CN、en-US 或 pt-BR")


class SettingsStore:
    def __init__(
        self,
        path: Path | None = None,
        data_dir: Path | None = None,
        secret_store: SecretStore | None = None,
    ) -> None:
        self.data_dir = data_dir or (path.parent if path else default_data_dir())
        self.path = path or self.data_dir / "config.json"
        self.secret_store = secret_store or SecretStore(self.data_dir / "api-key.dpapi")
        self.last_secret_error = ""

    def load(self) -> AppSettings:
        if not self.path.exists():
            return AppSettings()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"配置文件无法读取：{exc}") from exc
        settings = _settings_from_dict(raw)
        settings.validate()
        return settings

    def save(self, settings: AppSettings) -> None:
        settings.validate()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(settings)
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def load_api_key(self) -> str:
        environment_value = os.getenv("YIDA_AI_API_KEY", "").strip()
        if environment_value:
            self.last_secret_error = ""
            return environment_value
        try:
            value = self.secret_store.load()
        except SecretStoreError as exc:
            self.last_secret_error = str(exc)
            return ""
        self.last_secret_error = ""
        return value

    def save_api_key(self, api_key: str) -> None:
        self.secret_store.save(api_key)

    def clear_api_key(self) -> None:
        self.secret_store.clear()

    def has_saved_api_key(self) -> bool:
        return self.secret_store.exists


def _settings_from_dict(raw: dict[str, Any]) -> AppSettings:
    migrated = dict(raw)
    if "onboarding_completed" not in migrated:
        migrated["onboarding_completed"] = bool(migrated)
    aliases = {
        "source_language": "speech_language",
        "user_language": "translation_language",
        "ui_language": "interface_language",
    }
    for old_name, new_name in aliases.items():
        if new_name not in migrated and old_name in migrated:
            migrated[new_name] = migrated[old_name]
        migrated.pop(old_name, None)
    values = {
        key: value
        for key, value in migrated.items()
        if key not in {"llm", "adapter", "caption_source", "privacy"}
    }
    values["llm"] = LLMSettings(**migrated.get("llm", {}))
    source_values = migrated.get("caption_source", migrated.get("adapter", {}))
    values["caption_source"] = CaptionSourceSettings(**source_values)
    values["privacy"] = PrivacySettings(**migrated.get("privacy", {}))
    return AppSettings(**values)
