from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LanguageSpec:
    code: str
    display_name: str
    english_name: str
    live_captions_name_zh: str
    verified: bool


LANGUAGES: dict[str, LanguageSpec] = {
    "zh-CN": LanguageSpec("zh-CN", "简体中文", "Simplified Chinese", "简体中文(中国大陆)", True),
    "en-US": LanguageSpec("en-US", "英语（美国）", "English (US)", "英语(美国)", True),
    "pt-BR": LanguageSpec(
        "pt-BR", "葡萄牙语（巴西）", "Portuguese (Brazil)", "葡萄牙语(巴西)", True
    ),
}

VERIFIED_LANGUAGE_CODES = tuple(LANGUAGES)


def language_name(code: str) -> str:
    spec = LANGUAGES.get(code)
    return spec.display_name if spec else f"{code}（实验性）"
