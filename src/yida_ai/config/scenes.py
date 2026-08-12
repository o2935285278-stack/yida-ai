from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SceneTemplate:
    key: str
    name: str
    instruction: str
    speech_language: str = ""
    translation_language: str = ""
    reply_language: str = ""


SCENE_TEMPLATES: dict[str, SceneTemplate] = {
    "general": SceneTemplate("general", "通用交流", "回答自然、清楚、直接，并保持礼貌。"),
    "business": SceneTemplate("business", "商务交流", "保持专业，明确行动项，不虚构商务事实。"),
    "sales": SceneTemplate("sales", "销售沟通", "理解需求后建议下一步，不编造价格、库存或承诺。"),
    "customer_service": SceneTemplate(
        "customer_service", "客户服务", "先确认问题，再提供可执行且有依据的帮助。"
    ),
    "technical_support": SceneTemplate(
        "technical_support", "技术支持", "给出可验证的排查步骤，区分事实和假设。"
    ),
    "interview": SceneTemplate("interview", "面试", "依据候选人资料作答，不夸大或编造经历。"),
    "language_learning": SceneTemplate(
        "language_learning", "语言学习", "兼顾正确性、自然表达和简短解释。"
    ),
    "custom": SceneTemplate("custom", "自定义模板", "遵循用户配置的场景规则。"),
    "brazilian_customer": SceneTemplate(
        "brazilian_customer",
        "巴西客户",
        "理解巴西葡语客户的问题，依据资料给出简短自然的巴西葡语回答，不编造承诺。",
        "pt-BR",
        "zh-CN",
        "pt-BR",
    ),
    "english_customer": SceneTemplate(
        "english_customer",
        "英语客户",
        "理解英语客户的问题，依据资料给出简短自然的美式英语回答，不编造承诺。",
        "en-US",
        "zh-CN",
        "en-US",
    ),
    "chinese_speaker": SceneTemplate(
        "chinese_speaker",
        "中文发言",
        "准确理解中文发言，提供便于跨语言沟通的回答，不推测资料中不存在的事实。",
        "zh-CN",
        "en-US",
        "en-US",
    ),
    "chinese_to_brazilian": SceneTemplate(
        "chinese_to_brazilian",
        "中文发言（巴西葡语回复）",
        "准确理解中文发言，给出简短自然的巴西葡语回答，不推测资料中不存在的事实。",
        "zh-CN",
        "pt-BR",
        "pt-BR",
    ),
}
