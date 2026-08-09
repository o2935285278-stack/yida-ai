from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SceneTemplate:
    key: str
    name: str
    instruction: str


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
}
