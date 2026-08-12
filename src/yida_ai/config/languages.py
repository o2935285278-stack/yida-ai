from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LanguageSpec:
    code: str
    display_name: str
    english_name: str
    portuguese_name: str
    live_captions_name_zh: str
    verified: bool


LANGUAGES: dict[str, LanguageSpec] = {
    "zh-CN": LanguageSpec(
        "zh-CN",
        "简体中文",
        "Simplified Chinese",
        "Chinês simplificado",
        "简体中文(中国大陆)",
        True,
    ),
    "en-US": LanguageSpec(
        "en-US",
        "英语（美国）",
        "English (US)",
        "Inglês (Estados Unidos)",
        "英语(美国)",
        True,
    ),
    "pt-BR": LanguageSpec(
        "pt-BR",
        "葡萄牙语（巴西）",
        "Portuguese (Brazil)",
        "Português (Brasil)",
        "葡萄牙语(巴西)",
        True,
    ),
}

VERIFIED_LANGUAGE_CODES = tuple(LANGUAGES)
LANGUAGE_PRESETS = VERIFIED_LANGUAGE_CODES
LANGUAGE_DIRECTIONS = tuple(
    (source, target)
    for source in VERIFIED_LANGUAGE_CODES
    for target in VERIFIED_LANGUAGE_CODES
    if source != target
)

_BCP47_PATTERN = re.compile(r"^(?:[A-Za-z]{2,3})(?:-[A-Za-z0-9]{2,8})*$")


def validate_language_code(code: str) -> str:
    value = code.strip()
    if not _BCP47_PATTERN.fullmatch(value):
        raise ValueError(f"语言代码 {value or '（空）'} 不是有效的 BCP-47 格式")
    return value


def language_name(code: str, locale: str = "zh-CN") -> str:
    spec = LANGUAGES.get(code)
    if spec:
        if locale == "en-US":
            return spec.english_name
        if locale == "pt-BR":
            return spec.portuguese_name
        return spec.display_name
    suffix = {
        "en-US": "experimental",
        "pt-BR": "experimental",
    }.get(locale, "实验性")
    return f"{code} ({suffix})"


def validate_language_direction(source: str, target: str) -> tuple[str, str]:
    validate_language_code(source)
    validate_language_code(target)
    if source == target:
        raise ValueError("听取语言与翻译显示语言相同，不会产生跨语言翻译；请改选目标语言。")
    return source, target
