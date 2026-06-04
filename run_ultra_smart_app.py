import json
import os
from collections import defaultdict
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from PIL import Image, ImageStat
from pydantic import BaseModel, Field
import uvicorn


class PantryItem(BaseModel):
    name: str
    quantity: float = 1
    unit: str = "шт"
    expires_in_days: Optional[int] = None
    source: str = "manual"
    confidence: Optional[float] = None


class Nutrition(BaseModel):
    calories: int
    protein: float
    carbs: float
    fats: float


class Recipe(BaseModel):
    id: int
    title: str
    meal: str
    season_tags: List[str] = []
    ingredients: Dict[str, float]
    cost_per_serving: float
    servings: int = 1
    time_min: int = 15
    difficulty: str = "easy"
    nutrition: Nutrition


class SuggestRequest(BaseModel):
    pantry: List[PantryItem]
    budget: float = 500
    season: Optional[str] = None
    meal: Optional[str] = None


class PlanRequest(BaseModel):
    pantry: List[PantryItem]
    budget_per_day: float = Field(500, gt=0)
    season: Optional[str] = None
    target_calories: Optional[int] = 1800
    meal_preference: Optional[str] = "day"
    protein_goal_g: Optional[int] = 100
    carbs_goal_g: Optional[int] = 180
    fats_goal_g: Optional[int] = 60


class ThreeDayPlanRequest(PlanRequest):
    days: int = Field(3, ge=1, le=3)


class PlanResponse(BaseModel):
    meals: Dict[str, Recipe]
    totals: Dict[str, Any]
    shopping_gaps: List[str]
    notes: List[str]


class DetectedIngredient(BaseModel):
    name: str
    quantity: float = 1
    unit: str = "шт"
    expires_in_days: Optional[int] = None
    confidence: float = 0.5
    source: str = "fallback"
    reason: str


class VisionResponse(BaseModel):
    items: List[DetectedIngredient]
    raw_text: str = ""
    image_quality: Dict[str, Any]
    needs_confirmation: bool = True
    fallback: str
    notes: List[str]


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
    normalized_aliases = {k.replace("ё", "е"): v.replace("ё", "е") for k, v in PRODUCT_ALIASES.items()}
    return normalized_aliases.get(value, value)


def load_recipes() -> List[Recipe]:
    path = os.path.join("data", "recipes_ru.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as file:
            raw = json.load(file)
        recipes = []
        for item in raw:
            item.setdefault("season_tags", [])
            item.setdefault("servings", 1)
            item.setdefault("time_min", 20)
            item.setdefault("difficulty", "easy")
            recipes.append(Recipe(**item))
        return recipes
    raise RuntimeError("data/recipes_ru.json not found")


RECIPES = load_recipes()


def pantry_index(pantry: List[PantryItem]) -> Dict[str, PantryItem]:
    result: Dict[str, PantryItem] = {}
    for item in pantry:
        key = normalize_name(item.name)
        if key:
            result[key] = item
    return result


def has_ingredients(recipe: Recipe, idx: Dict[str, PantryItem]) -> Tuple[bool, List[str]]:
    missing = []
    for name, need in recipe.ingredients.items():
        key = normalize_name(name)
        pantry_item = idx.get(key)
        if pantry_item is None or pantry_item.quantity < float(need or 0):
            missing.append(name)
    return len(missing) == 0, missing


def season_ok(recipe: Recipe, season: Optional[str]) -> bool:
    return not season or season in recipe.season_tags


def expiry_priority(recipe: Recipe, idx: Dict[str, PantryItem]) -> int:
    values = []
    for name in recipe.ingredients:
        item = idx.get(normalize_name(name))
        if item and item.expires_in_days is not None:
            values.append(max(0, item.expires_in_days))
    return min(values) if values else 999


def score_recipe(recipe: Recipe, idx: Dict[str, PantryItem], season: Optional[str], used_recipe_ids: set[int]) -> float:
    _, missing = has_ingredients(recipe, idx)
    score = max(0, 80 - 12 * len(missing))
    if not missing:
        score += 40
    if season_ok(recipe, season):
        score += 15
    score += max(0, 20 - expiry_priority(recipe, idx))
    score += max(0, 20 - recipe.time_min / 3)
    if recipe.id in used_recipe_ids:
        score -= 35
    return score


def sum_nutrition(recipes: List[Recipe]) -> Dict[str, float]:
    return {
        "calories": sum(recipe.nutrition.calories for recipe in recipes),
        "protein_g": round(sum(recipe.nutrition.protein for recipe in recipes), 1),
        "carbs_g": round(sum(recipe.nutrition.carbs for recipe in recipes), 1),
        "fats_g": round(sum(recipe.nutrition.fats for recipe in recipes), 1),
    }


def pick_recipe(
    meal: str,
    idx: Dict[str, PantryItem],
    season: Optional[str],
    budget_left: float,
    used_recipe_ids: set[int],
) -> Recipe:
    candidates = [recipe for recipe in RECIPES if recipe.meal == meal and season_ok(recipe, season)]
    if not candidates:
        raise HTTPException(404, f"Нет рецептов для типа приема пищи: {meal}")
    ranked = sorted(
        candidates,
        key=lambda recipe: (-score_recipe(recipe, idx, season, used_recipe_ids), recipe.cost_per_serving),
    )
    for recipe in ranked:
        if recipe.cost_per_serving <= budget_left:
            used_recipe_ids.add(recipe.id)
            return recipe
    used_recipe_ids.add(ranked[0].id)
    return ranked[0]


def recipe_reasons(recipe: Recipe, idx: Dict[str, PantryItem]) -> List[str]:
    _, missing = has_ingredients(recipe, idx)
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


def build_shopping_list(recipes: List[Recipe], pantry: List[PantryItem]) -> List[Dict[str, Any]]:
    idx = pantry_index(pantry)
    needs: Dict[str, Dict[str, Any]] = {}
    for recipe in recipes:
        for ingredient, need in recipe.ingredients.items():
            key = normalize_name(ingredient)
            have = idx.get(key).quantity if key in idx else 0
            missing = max(0.0, float(need or 0) - float(have or 0))
            if missing <= 0:
                continue
            if key not in needs:
                needs[key] = {
                    "name": ingredient,
                    "category": PRODUCT_CATEGORIES.get(key, "Прочее"),
                    "missing_quantity": 0.0,
                    "unit": "порция",
                    "needed_for": [],
                    "reason": "",
                }
            needs[key]["missing_quantity"] += missing
            if recipe.title not in needs[key]["needed_for"]:
                needs[key]["needed_for"].append(recipe.title)

    result = []
    for item in needs.values():
        item["missing_quantity"] = round(item["missing_quantity"], 2)
        item["reason"] = "Нужно для блюд: " + ", ".join(item["needed_for"][:3])
        result.append(item)
    return sorted(result, key=lambda value: (value["category"], value["name"]))


def build_three_day_plan(req: ThreeDayPlanRequest) -> Dict[str, Any]:
    idx = pantry_index(req.pantry)
    used_recipe_ids: set[int] = set()
    days = []
    all_recipes: List[Recipe] = []
    notes: List[str] = []

    for day_number in range(1, req.days + 1):
        day_meals = {}
        day_recipes = []
        budget_left = req.budget_per_day

        for meal in ["breakfast", "lunch", "dinner"]:
            recipe = pick_recipe(meal, idx, req.season, budget_left, used_recipe_ids)
            day_meals[meal] = {
                "label": MEAL_LABELS[meal],
                "recipe": recipe.model_dump(),
                "reasons": recipe_reasons(recipe, idx),
            }
            budget_left -= recipe.cost_per_serving
            day_recipes.append(recipe)
            all_recipes.append(recipe)

        totals = sum_nutrition(day_recipes)
        totals["cost"] = round(sum(recipe.cost_per_serving for recipe in day_recipes), 2)
        days.append(
            {
                "day": day_number,
                "title": f"День {day_number}",
                "meals": day_meals,
                "totals": totals,
            }
        )

    shopping_list = build_shopping_list(all_recipes, req.pantry)
    totals = sum_nutrition(all_recipes)
    totals["cost"] = round(sum(recipe.cost_per_serving for recipe in all_recipes), 2)
    totals["budget_limit"] = round(req.budget_per_day * req.days, 2)
    totals["target_calories"] = (req.target_calories or 0) * req.days

    used_ingredients = {normalize_name(name) for recipe in all_recipes for name in recipe.ingredients}
    pantry_ingredients = {normalize_name(item.name) for item in req.pantry}
    used_from_pantry = used_ingredients & pantry_ingredients
    pantry_usage = round(len(used_from_pantry) / max(1, len(pantry_ingredients)) * 100, 1)

    if totals["protein_g"] < (req.protein_goal_g or 0) * req.days * 0.8:
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
            "recipes_count": len(all_recipes),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        },
        "notes": notes,
    }


def image_quality(image: Image.Image) -> Dict[str, Any]:
    gray = image.convert("L")
    stat = ImageStat.Stat(gray)
    brightness = round(stat.mean[0], 2)
    contrast = round(stat.stddev[0], 2)
    return {
        "width": image.width,
        "height": image.height,
        "brightness": brightness,
        "contrast": contrast,
        "overall": "good" if 45 <= brightness <= 220 and contrast >= 25 else "needs_review",
    }


def color_fallback_detection(image: Image.Image) -> List[DetectedIngredient]:
    small = image.convert("RGB").resize((80, 80))
    pixels = list(small.getdata())
    red = sum(1 for r, g, b in pixels if r > 140 and g < 120 and b < 120)
    green = sum(1 for r, g, b in pixels if g > 120 and r < 130)
    yellow = sum(1 for r, g, b in pixels if r > 150 and g > 130 and b < 100)
    white = sum(1 for r, g, b in pixels if r > 190 and g > 190 and b > 180)
    total = max(1, len(pixels))

    detected: List[DetectedIngredient] = []
    if red / total > 0.05:
        detected.append(DetectedIngredient(name="помидор", confidence=0.58, source="color_fallback", reason="на фото заметны красные области"))
    if green / total > 0.08:
        detected.append(DetectedIngredient(name="огурец", confidence=0.52, source="color_fallback", reason="на фото заметны зеленые области"))
    if yellow / total > 0.06:
        detected.append(DetectedIngredient(name="банан", confidence=0.5, source="color_fallback", reason="на фото заметны желтые области"))
    if white / total > 0.12:
        detected.append(DetectedIngredient(name="йогурт", confidence=0.45, source="color_fallback", reason="на фото много светлых упаковок или продуктов"))
    return detected


def text_fallback_detection(text: str) -> List[DetectedIngredient]:
    found = []
    normalized_text = normalize_name(text)
    known_products = set(PRODUCT_CATEGORIES) | {"яйца", "помидор", "огурец", "курица", "йогурт", "творог"}
    for product in sorted(known_products):
        if product in normalized_text:
            found.append(
                DetectedIngredient(
                    name=product,
                    confidence=0.82,
                    source="text_hint",
                    reason="найдено в текстовой подсказке или названии файла",
                )
            )
    return found


app = FastAPI(title="Fridge-to-Meal Planner AI", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "ok": True,
        "name": "Fridge-to-Meal Planner AI",
        "version": "0.3.0",
        "docs": "/docs",
        "app": "/app",
        "recipes": len(RECIPES),
    }


@app.get("/app")
def frontend():
    index_path = os.path.join(os.getcwd(), "index.html")
    if not os.path.exists(index_path):
        raise HTTPException(404, "index.html not found")
    return FileResponse(index_path)


@app.get("/api/v2/demo")
def demo():
    return {
        "pantry": [item.model_dump() for item in DEMO_PANTRY],
        "preferences": {
            "budget_per_day": 520,
            "season": None,
            "target_calories": 1800,
            "protein_goal_g": 95,
            "meal_preference": "day",
        },
        "scenario": "Demo: фото холодильника дает кандидатов, пользователь подтверждает продукты, затем система строит план на 3 дня.",
    }


@app.get("/api/v2/recipes/sample")
def sample_recipes(n: int = 12):
    return [recipe.model_dump() for recipe in RECIPES[: max(1, min(n, len(RECIPES)))]]


@app.post("/api/v2/suggest")
def suggest(req: SuggestRequest) -> Recipe:
    idx = pantry_index(req.pantry)
    candidates = [recipe for recipe in RECIPES if (req.meal is None or recipe.meal == req.meal) and season_ok(recipe, req.season)]
    if not candidates:
        raise HTTPException(404, "Нет подходящих рецептов")
    ranked = sorted(candidates, key=lambda recipe: (-score_recipe(recipe, idx, req.season, set()), recipe.cost_per_serving))
    for recipe in ranked:
        if recipe.cost_per_serving <= req.budget:
            return recipe
    return ranked[0]


@app.post("/api/v2/plan")
def plan(req: PlanRequest) -> PlanResponse:
    idx = pantry_index(req.pantry)
    meals: Dict[str, Recipe] = {}
    used_recipe_ids: set[int] = set()
    if req.meal_preference in ("breakfast", "lunch", "dinner"):
        meals[req.meal_preference] = pick_recipe(req.meal_preference, idx, req.season, req.budget_per_day, used_recipe_ids)
    else:
        budget_left = req.budget_per_day
        for meal in ["breakfast", "lunch", "dinner"]:
            recipe = pick_recipe(meal, idx, req.season, budget_left, used_recipe_ids)
            meals[meal] = recipe
            budget_left -= recipe.cost_per_serving

    recipes = list(meals.values())
    totals = sum_nutrition(recipes)
    totals["cost"] = round(sum(recipe.cost_per_serving for recipe in recipes), 2)
    totals["target_calories"] = req.target_calories
    totals["budget_limit"] = req.budget_per_day
    shopping = build_shopping_list(recipes, req.pantry)
    notes = [item["reason"] for item in shopping[:3]]
    return PlanResponse(
        meals=meals,
        totals=totals,
        shopping_gaps=[item["name"] for item in shopping],
        notes=notes,
    )


@app.post("/api/v2/meal-plan/3-days")
def three_day_plan(req: ThreeDayPlanRequest):
    req.days = 3
    return build_three_day_plan(req)


@app.post("/api/v2/vision/analyze", response_model=VisionResponse)
async def analyze_photo(
    file: UploadFile = File(...),
    mode: str = Form("auto"),
    text_hint: str = Form(""),
):
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(400, "Загрузите изображение")

    content = await file.read()
    if len(content) > 8 * 1024 * 1024:
        raise HTTPException(400, "Файл слишком большой. Лимит MVP: 8 MB")

    try:
        image = Image.open(BytesIO(content)).convert("RGB")
    except Exception as exc:
        raise HTTPException(400, "Не удалось прочитать изображение") from exc

    quality = image_quality(image)
    notes = [
        "MVP использует простую эвристику по цветам и текстовую подсказку.",
        "Перед добавлением в холодильник продукты нужно подтвердить вручную.",
    ]

    if mode == "demo":
        return VisionResponse(
            items=[
                DetectedIngredient(name=item.name, quantity=item.quantity, unit=item.unit, expires_in_days=item.expires_in_days, confidence=item.confidence or 0.8, source="demo", reason="демо-сценарий")
                for item in DEMO_PANTRY[:5]
            ],
            raw_text=text_hint,
            image_quality=quality,
            fallback="demo",
            notes=notes,
        )

    candidates = text_fallback_detection(f"{file.filename or ''} {text_hint}")
    candidates.extend(color_fallback_detection(image))

    by_name: Dict[str, DetectedIngredient] = {}
    for item in candidates:
        key = normalize_name(item.name)
        if key not in by_name or by_name[key].confidence < item.confidence:
            by_name[key] = item

    items = list(by_name.values())
    if not items:
        items = [
            DetectedIngredient(name=item.name, quantity=item.quantity, unit=item.unit, expires_in_days=item.expires_in_days, confidence=0.6, source="fallback_demo", reason="CV не нашел уверенных объектов, подставлен безопасный demo-набор")
            for item in DEMO_PANTRY[:4]
        ]
        fallback = "demo_pantry"
        notes.append("Распознавание не уверено: используйте список как черновик.")
    else:
        fallback = "color_text_heuristics"

    return VisionResponse(
        items=items,
        raw_text=text_hint,
        image_quality=quality,
        fallback=fallback,
        notes=notes,
    )


if __name__ == "__main__":
    print("Fridge-to-Meal Planner AI: http://127.0.0.1:8000/app")
    uvicorn.run(app, host="127.0.0.1", port=8000)
