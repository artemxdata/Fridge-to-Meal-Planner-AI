from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from app.catalog import MEAL_LABELS, PRODUCT_CATEGORIES, normalize_name, recipes
from app.schemas import (
    DecisionTraceItem,
    PantryItem,
    PlanOption,
    PlanOptionsRequest,
    PlanOptionsResponse,
    PlanRequest,
    PlanResponse,
    PlanStrategy,
    Recipe,
    SuggestRequest,
    ThreeDayPlanRequest,
)


class RecipeNotFoundError(LookupError):
    pass


def pantry_index(pantry: list[PantryItem]) -> dict[str, PantryItem]:
    result: dict[str, PantryItem] = {}
    for item in pantry:
        key = normalize_name(item.name)
        if not key:
            continue
        existing = result.get(key)
        if existing:
            existing.quantity += item.quantity
            if item.expires_in_days is not None:
                current_expiry = existing.expires_in_days
                existing.expires_in_days = (
                    item.expires_in_days
                    if current_expiry is None
                    else min(current_expiry, item.expires_in_days)
                )
        else:
            result[key] = item.model_copy(deep=True)
    return result


def missing_ingredients(recipe: Recipe, idx: dict[str, PantryItem]) -> list[str]:
    missing = []
    for name, need in recipe.ingredients.items():
        pantry_item = idx.get(normalize_name(name))
        if pantry_item is None or pantry_item.quantity < float(need or 0):
            missing.append(name)
    return missing


def season_ok(recipe: Recipe, season: str | None) -> bool:
    return not season or season in recipe.season_tags


def expiry_priority(recipe: Recipe, idx: dict[str, PantryItem]) -> int:
    values = [
        max(0, item.expires_in_days)
        for name in recipe.ingredients
        if (item := idx.get(normalize_name(name))) is not None and item.expires_in_days is not None
    ]
    return min(values) if values else 999


def score_recipe(
    recipe: Recipe,
    idx: dict[str, PantryItem],
    season: str | None,
    used_recipe_ids: set[int],
    strategy: PlanStrategy = "balanced",
) -> float:
    missing = missing_ingredients(recipe, idx)
    score = max(0, 80 - 12 * len(missing))
    if not missing:
        score += 40
    if season_ok(recipe, season):
        score += 15
    score += max(0, 20 - expiry_priority(recipe, idx))
    score += max(0, 20 - recipe.time_min / 3)
    if strategy == "simple":
        score += max(0, 60 - recipe.time_min * 2)
        score -= len(recipe.ingredients) * 2
    elif strategy == "waste_first":
        score += max(0, 60 - expiry_priority(recipe, idx) * 4)
        score += max(0, 30 - len(missing) * 8)
    if recipe.id in used_recipe_ids:
        score -= 35
    return score


def sum_nutrition(selected_recipes: list[Recipe]) -> dict[str, float]:
    return {
        "calories": sum(recipe.nutrition.calories for recipe in selected_recipes),
        "protein_g": round(sum(recipe.nutrition.protein for recipe in selected_recipes), 1),
        "carbs_g": round(sum(recipe.nutrition.carbs for recipe in selected_recipes), 1),
        "fats_g": round(sum(recipe.nutrition.fats for recipe in selected_recipes), 1),
    }


def pick_recipe(
    meal: str,
    idx: dict[str, PantryItem],
    season: str | None,
    budget_left: float,
    used_recipe_ids: set[int],
    strategy: PlanStrategy = "balanced",
) -> Recipe:
    candidates = [recipe for recipe in recipes() if recipe.meal == meal and season_ok(recipe, season)]
    if not candidates:
        raise RecipeNotFoundError(f"Нет рецептов для типа приёма пищи: {meal}")

    ranked = sorted(
        candidates,
        key=lambda recipe: (
            -score_recipe(recipe, idx, season, used_recipe_ids, strategy),
            recipe.cost_per_serving,
        ),
    )
    selected = next((recipe for recipe in ranked if recipe.cost_per_serving <= budget_left), ranked[0])
    used_recipe_ids.add(selected.id)
    return selected


def recipe_reasons(recipe: Recipe, idx: dict[str, PantryItem]) -> list[str]:
    missing = missing_ingredients(recipe, idx)
    available = [name for name in recipe.ingredients if normalize_name(name) in idx]
    reasons = []
    if available:
        reasons.append("использует продукты из холодильника: " + ", ".join(available[:4]))
    if missing:
        reasons.append("нужно докупить: " + ", ".join(missing[:4]))
    if expiry_priority(recipe, idx) <= 3:
        reasons.append("помогает использовать продукты с коротким сроком годности")
    if recipe.time_min <= 20:
        reasons.append("быстро готовится")
    if recipe.nutrition.protein >= 20:
        reasons.append("поддерживает цель по белку")
    return reasons or ["сбалансированное блюдо под текущие ограничения"]


def build_shopping_list(selected_recipes: list[Recipe], pantry: list[PantryItem]) -> list[dict[str, Any]]:
    idx = pantry_index(pantry)
    required: defaultdict[str, float] = defaultdict(float)
    recipe_titles: defaultdict[str, list[str]] = defaultdict(list)
    display_names: dict[str, str] = {}

    for recipe in selected_recipes:
        for ingredient, amount in recipe.ingredients.items():
            key = normalize_name(ingredient)
            required[key] += float(amount or 0)
            display_names[key] = ingredient
            if recipe.title not in recipe_titles[key]:
                recipe_titles[key].append(recipe.title)

    result = []
    for key, amount in required.items():
        have = idx.get(key).quantity if key in idx else 0
        missing = max(0.0, amount - float(have or 0))
        if missing <= 0:
            continue
        result.append(
            {
                "name": display_names[key],
                "category": PRODUCT_CATEGORIES.get(key, "Прочее"),
                "missing_quantity": round(missing, 2),
                "unit": "порция",
                "needed_for": recipe_titles[key],
                "reason": "Нужно для блюд: " + ", ".join(recipe_titles[key][:3]),
            }
        )
    return sorted(result, key=lambda item: (item["category"], item["name"]))


def suggest_recipe(request: SuggestRequest) -> Recipe:
    idx = pantry_index(request.pantry)
    candidates = [
        recipe
        for recipe in recipes()
        if (request.meal is None or recipe.meal == request.meal) and season_ok(recipe, request.season)
    ]
    if not candidates:
        raise RecipeNotFoundError("Нет подходящих рецептов")
    ranked = sorted(
        candidates,
        key=lambda recipe: (-score_recipe(recipe, idx, request.season, set()), recipe.cost_per_serving),
    )
    return next((recipe for recipe in ranked if recipe.cost_per_serving <= request.budget), ranked[0])


def build_daily_plan(request: PlanRequest) -> PlanResponse:
    idx = pantry_index(request.pantry)
    meals: dict[str, Recipe] = {}
    used_recipe_ids: set[int] = set()

    if request.meal_preference in ("breakfast", "lunch", "dinner"):
        meal = request.meal_preference
        meals[meal] = pick_recipe(meal, idx, request.season, request.budget_per_day, used_recipe_ids)
    else:
        budget_left = request.budget_per_day
        for meal in ("breakfast", "lunch", "dinner"):
            recipe = pick_recipe(meal, idx, request.season, budget_left, used_recipe_ids)
            meals[meal] = recipe
            budget_left -= recipe.cost_per_serving

    selected_recipes = list(meals.values())
    totals: dict[str, Any] = sum_nutrition(selected_recipes)
    totals["cost"] = round(sum(recipe.cost_per_serving for recipe in selected_recipes), 2)
    totals["target_calories"] = request.target_calories
    totals["budget_limit"] = request.budget_per_day
    shopping = build_shopping_list(selected_recipes, request.pantry)
    return PlanResponse(
        meals=meals,
        totals=totals,
        shopping_gaps=[item["name"] for item in shopping],
        notes=[item["reason"] for item in shopping[:3]],
    )


def build_three_day_plan(
    request: ThreeDayPlanRequest,
    strategy: PlanStrategy = "balanced",
) -> dict[str, Any]:
    idx = pantry_index(request.pantry)
    used_recipe_ids: set[int] = set()
    days = []
    selected_recipes: list[Recipe] = []
    notes: list[str] = []

    for day_number in range(1, request.days + 1):
        day_meals = {}
        day_recipes = []
        budget_left = request.budget_per_day
        for meal in ("breakfast", "lunch", "dinner"):
            recipe = pick_recipe(meal, idx, request.season, budget_left, used_recipe_ids, strategy)
            day_meals[meal] = {
                "label": MEAL_LABELS[meal],
                "recipe": recipe.model_dump(),
                "reasons": recipe_reasons(recipe, idx),
            }
            budget_left -= recipe.cost_per_serving
            day_recipes.append(recipe)
            selected_recipes.append(recipe)

        totals: dict[str, Any] = sum_nutrition(day_recipes)
        totals["cost"] = round(sum(recipe.cost_per_serving for recipe in day_recipes), 2)
        days.append({"day": day_number, "title": f"День {day_number}", "meals": day_meals, "totals": totals})

    shopping_list = build_shopping_list(selected_recipes, request.pantry)
    totals = sum_nutrition(selected_recipes)
    totals["cost"] = round(sum(recipe.cost_per_serving for recipe in selected_recipes), 2)
    totals["budget_limit"] = round(request.budget_per_day * request.days, 2)
    totals["target_calories"] = (request.target_calories or 0) * request.days

    used_ingredients = {normalize_name(name) for recipe in selected_recipes for name in recipe.ingredients}
    pantry_ingredients = {normalize_name(item.name) for item in request.pantry}
    used_from_pantry = used_ingredients & pantry_ingredients
    pantry_usage = round(len(used_from_pantry) / max(1, len(pantry_ingredients)) * 100, 1)

    if totals["protein_g"] < (request.protein_goal_g or 0) * request.days * 0.8:
        notes.append("Белка может быть маловато: добавьте творог, йогурт, яйца или курицу.")
    if totals["cost"] > totals["budget_limit"]:
        notes.append("План выходит за бюджет: замените одно дорогое блюдо на кашу, суп или овощной вариант.")
    if shopping_list:
        notes.append("Список покупок сформирован только по недостающим ингредиентам.")

    return {
        "days": days,
        "totals": totals,
        "shopping_list": shopping_list,
        "statistics": {
            "pantry_usage_percent": pantry_usage,
            "pantry_items_used": sorted(used_from_pantry),
            "recipes_count": len(selected_recipes),
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        },
        "notes": notes,
    }


def build_plan_options(request: PlanOptionsRequest) -> PlanOptionsResponse:
    definitions: list[tuple[PlanStrategy, str, str]] = [
        (
            "simple",
            "Проще готовить",
            "Приоритет короткому времени приготовления и небольшому числу ингредиентов.",
        ),
        (
            "waste_first",
            "Сначала использовать продукты",
            "Приоритет продуктам с коротким сроком годности и минимальным докупкам.",
        ),
        (
            "balanced",
            "Сбалансированный вариант",
            "Компромисс между временем, использованием pantry, бюджетом и разнообразием.",
        ),
    ]
    options = []
    for strategy, title, summary in definitions:
        plan = build_three_day_plan(request, strategy)
        trace = [
            DecisionTraceItem(
                rule=f"strategy:{strategy}",
                reason=summary,
                evidence={
                    "pantry_usage_percent": plan["statistics"]["pantry_usage_percent"],
                    "estimated_cost": plan["totals"]["cost"],
                    "budget_limit": plan["totals"]["budget_limit"],
                },
            ),
            DecisionTraceItem(
                rule="human_approval_required",
                reason="План является черновиком и не изменяет pantry или список покупок без подтверждения.",
                evidence={"approval_status": "draft"},
            ),
        ]
        if request.context_note:
            trace.insert(
                1,
                DecisionTraceItem(
                    rule="user_context_recorded",
                    reason="Контекст пользователя сохранён как объясняющая подсказка, но не применён скрыто.",
                    evidence={"context_note": request.context_note},
                ),
            )
        options.append(
            PlanOption(
                option_id=f"draft-{strategy}",
                strategy=strategy,
                title=title,
                summary=summary,
                plan=plan,
                decision_trace=trace,
            )
        )
    return PlanOptionsResponse(
        options=options,
        assistant_boundary=(
            "Система предлагает объяснимые черновики. Пользователь выбирает и подтверждает итоговый план."
        ),
    )
