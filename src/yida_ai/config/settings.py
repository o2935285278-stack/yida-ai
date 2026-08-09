from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


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

    @property
    def api_key(self) -> str:
        return os.getenv("YIDA_AI_API_KEY", "").strip()


@dataclass(slots=True)
class AdapterSettings:
    kind: str = "livecaptions-translator"
    database_path: str = ""
    poll_interval_ms: int = 180


@dataclass(slots=True)
class PrivacySettings:
    save_history: bool = True
    retention_days: int = 30


@dataclass(slots=True)
class AppSettings:
    source_language: str = "pt-BR"
    user_language: str = "zh-CN"
    reply_language: str = "pt-BR"
    scene: str = "general"
    custom_scene_instruction: str = ""
    reply_mode: str = "every"
    reply_length: str = "short"
    context_turns: int = 15
    llm: LLMSettings = field(default_factory=LLMSettings)
    adapter: AdapterSettings = field(default_factory=AdapterSettings)
    privacy: PrivacySettings = field(default_factory=PrivacySettings)

    def validate(self) -> None:
        if not 1 <= self.context_turns <= 50:
            raise ValueError("最近对话轮数必须在 1 到 50 之间")
        if not 0 <= self.privacy.retention_days <= 3650:
            raise ValueError("数据保留期限必须在 0 到 3650 天之间")
        if self.reply_mode not in {"translation", "auto", "every", "confirm"}:
            raise ValueError("未知回复模式")
        if self.reply_length not in {"short", "medium", "detailed"}:
            raise ValueError("未知回复长度")


class SettingsStore:
    def __init__(self, path: Path | None = None, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or (path.parent if path else default_data_dir())
        self.path = path or self.data_dir / "config.json"

    def load(self) -> AppSettings:
        if not self.path.exists():
            return AppSettings()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
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


def _settings_from_dict(raw: dict[str, Any]) -> AppSettings:
    values = {key: value for key, value in raw.items() if key not in {"llm", "adapter", "privacy"}}
    values["llm"] = LLMSettings(**raw.get("llm", {}))
    values["adapter"] = AdapterSettings(**raw.get("adapter", {}))
    values["privacy"] = PrivacySettings(**raw.get("privacy", {}))
    return AppSettings(**values)
