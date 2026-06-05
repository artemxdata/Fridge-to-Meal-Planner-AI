from __future__ import annotations

from typing import Any

from app.schemas import ContextInterpretResponse

RULES: tuple[tuple[tuple[str, ...], dict[str, Any], str], ...] = (
    (
        ("устал", "нет сил", "tired", "exhausted"),
        {"max_active_time_min": 15, "cleanup_level": "low"},
        "Фраза указывает на низкий запас сил: предложено сократить активное время и уборку.",
    ),
    (
        ("без магазина", "не покупать", "no shopping", "without shopping"),
        {"shopping_allowed": False},
        "Пользователь явно просит обойтись без дополнительных покупок.",
    ),
    (
        ("быстро", "15 минут", "quick", "fast"),
        {"max_active_time_min": 15},
        "Пользователь просит быстрый вариант.",
    ),
    (
        ("уют", "тёпл", "comfort", "cozy", "warm"),
        {"meal_mood": "comfort"},
        "Пользователь явно описывает желаемое настроение блюда.",
    ),
    (
        ("мало посуды", "без посуды", "one pot", "few dishes"),
        {"cleanup_level": "low"},
        "Пользователь просит минимизировать уборку после готовки.",
    ),
)


def interpret_context(text: str) -> ContextInterpretResponse:
    normalized = text.strip().lower()
    proposed: dict[str, Any] = {}
    evidence = []
    for keywords, constraints, reason in RULES:
        if any(keyword in normalized for keyword in keywords):
            proposed.update(constraints)
            evidence.append(reason)
    if not evidence:
        evidence.append("Явные ограничения не найдены; текст сохранён только как пользовательский контекст.")
    return ContextInterpretResponse(
        proposed_constraints=proposed,
        evidence=evidence,
    )
