from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.catalog import DEMO_PANTRY, recipes
from app.config import settings
from app.schemas import PlanRequest, PlanResponse, Recipe, SuggestRequest, ThreeDayPlanRequest, VisionResponse
from app.services.planner import RecipeNotFoundError, build_daily_plan, build_three_day_plan, suggest_recipe
from app.services.vision import ImageTooLargeError, InvalidImageError, analyze_image, decode_image

router = APIRouter(prefix="/api/v2", tags=["MVP v2"])


@router.get("/demo")
def demo() -> dict:
    return {
        "pantry": [item.model_dump() for item in DEMO_PANTRY],
        "preferences": {
            "budget_per_day": 520,
            "season": None,
            "target_calories": 1800,
            "protein_goal_g": 95,
            "meal_preference": "day",
        },
        "scenario": (
            "Demo: фото холодильника даёт кандидатов, пользователь подтверждает продукты, "
            "затем система строит план на 3 дня."
        ),
    }


@router.get("/recipes/sample", response_model=list[Recipe])
def sample_recipes(n: int = 12) -> list[Recipe]:
    return list(recipes()[: max(1, min(n, len(recipes())))])


@router.post("/suggest", response_model=Recipe)
def suggest(request: SuggestRequest) -> Recipe:
    try:
        return suggest_recipe(request)
    except RecipeNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.post("/plan", response_model=PlanResponse)
def plan(request: PlanRequest) -> PlanResponse:
    try:
        return build_daily_plan(request)
    except RecipeNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.post("/meal-plan/3-days")
def three_day_plan(request: ThreeDayPlanRequest) -> dict:
    try:
        request.days = 3
        return build_three_day_plan(request)
    except RecipeNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.post("/vision/analyze", response_model=VisionResponse)
async def analyze_photo(
    file: Annotated[UploadFile, File()],
    mode: Annotated[str, Form()] = "auto",
    text_hint: Annotated[str, Form()] = "",
) -> VisionResponse:
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Загрузите изображение")
    if mode not in {"auto", "demo"}:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "mode должен быть auto или demo")

    content = await file.read(settings.max_upload_bytes + 1)
    try:
        image = decode_image(content)
    except ImageTooLargeError as exc:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, str(exc)) from exc
    except InvalidImageError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    finally:
        await file.close()

    return analyze_image(
        image,
        filename=file.filename or "",
        text_hint=text_hint[:1000],
        mode=mode,
    )
