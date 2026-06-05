from __future__ import annotations

import json
from functools import lru_cache

from app.config import settings
from app.schemas import PantryItem, Recipe

MEAL_LABELS = {
    "breakfast": "Завтрак",
    "lunch": "Обед",
    "dinner": "Ужин",
}

PRODUCT_ALIASES = {
    "помидоры": "помидор",
    "томат": "помидор",
    "томаты": "помидор",
    "куриное филе": "курица",
    "куриная грудка": "курица",
    "яйцо": "яйца",
    "картошка": "картофель",
    "макароны": "паста",
    "овес": "овсянка",
    "геркулес": "овсянка",
    "творог 5%": "творог",
    "кефир 1%": "кефир",
}

PRODUCT_CATEGORIES = {
    "курица": "Белок",
    "говядина": "Белок",
    "рыба": "Белок",
    "яйца": "Белок",
    "тофу": "Белок",
    "творог": "Молочные",
    "йогурт": "Молочные",
    "кефир": "Молочные",
    "сметана": "Молочные",
    "сыр": "Молочные",
    "молоко": "Молочные",
    "картофель": "Овощи",
    "морковь": "Овощи",
    "лук": "Овощи",
    "помидор": "Овощи",
    "огурец": "Овощи",
    "перец": "Овощи",
    "капуста": "Овощи",
    "брокколи": "Овощи",
    "свекла": "Овощи",
    "салат": "Овощи",
    "яблоко": "Фрукты",
    "банан": "Фрукты",
    "гречка": "Крупы",
    "рис": "Крупы",
    "киноа": "Крупы",
    "овсянка": "Крупы",
    "паста": "Крупы",
    "мука": "Бакалея",
    "сахар": "Бакалея",
    "мёд": "Бакалея",
    "масло растительное": "Бакалея",
    "специи": "Бакалея",
}

DEMO_PANTRY = [
    PantryItem(name="яйца", quantity=6, unit="шт", expires_in_days=5, source="demo", confidence=0.96),
    PantryItem(name="йогурт", quantity=2, unit="шт", expires_in_days=3, source="demo", confidence=0.92),
    PantryItem(name="курица", quantity=1, unit="порция", expires_in_days=2, source="demo", confidence=0.86),
    PantryItem(name="картофель", quantity=4, unit="шт", expires_in_days=12, source="demo", confidence=0.82),
    PantryItem(name="морковь", quantity=2, unit="шт", expires_in_days=10, source="demo", confidence=0.78),
    PantryItem(name="лук", quantity=2, unit="шт", expires_in_days=15, source="demo", confidence=0.74),
]


def normalize_name(name: str) -> str:
    value = (name or "").strip().lower().replace("ё", "е")
    aliases = {key.replace("ё", "е"): item.replace("ё", "е") for key, item in PRODUCT_ALIASES.items()}
    return aliases.get(value, value)


@lru_cache(maxsize=1)
def load_recipes() -> tuple[Recipe, ...]:
    if not settings.recipes_path.exists():
        raise RuntimeError(f"Recipe catalog not found: {settings.recipes_path}")
    with settings.recipes_path.open("r", encoding="utf-8") as file:
        raw = json.load(file)
    return tuple(Recipe.model_validate(item) for item in raw)


def recipes() -> tuple[Recipe, ...]:
    return load_recipes()
