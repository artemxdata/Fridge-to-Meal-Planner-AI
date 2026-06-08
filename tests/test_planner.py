from app.schemas import PantryItem, Recipe
from app.services.planner import build_shopping_list


def test_shopping_list_aggregates_need_before_subtracting_pantry() -> None:
    recipe = Recipe.model_validate(
        {
            "id": 1,
            "title": "Тестовый омлет",
            "meal": "breakfast",
            "ingredients": {"яйца": 2},
            "cost_per_serving": 50,
            "nutrition": {"calories": 100, "protein": 10, "carbs": 2, "fats": 5},
        }
    )

    shopping = build_shopping_list([recipe, recipe], [PantryItem(name="яйца", quantity=3)])

    assert len(shopping) == 1
    assert shopping[0]["name"] == "яйца"
    assert shopping[0]["missing_quantity"] == 1


def test_shopping_list_normalizes_english_pantry_aliases() -> None:
    recipe = Recipe.model_validate(
        {
            "id": 1,
            "title": "Test omelet",
            "meal": "breakfast",
            "ingredients": {"яйца": 4},
            "cost_per_serving": 50,
            "nutrition": {"calories": 100, "protein": 10, "carbs": 2, "fats": 5},
        }
    )

    shopping = build_shopping_list([recipe], [PantryItem(name="eggs", quantity=3)])

    assert len(shopping) == 1
    assert shopping[0]["name"] == "яйца"
    assert shopping[0]["missing_quantity"] == 1
