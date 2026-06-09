from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AcceptedPlan, ConsumptionEvent, now_utc
from app.schemas import (
    ConsumptionEventCreateRequest,
    ConsumptionEventResponse,
    ConsumptionRecordResponse,
)
from app.services.households import create_audit_event


def _iso(value) -> str:
    return value.isoformat(timespec="seconds")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def consumption_event_response(event: ConsumptionEvent) -> ConsumptionEventResponse:
    return ConsumptionEventResponse(
        id=event.id,
        household_id=event.household_id,
        accepted_plan_id=event.accepted_plan_id,
        day=event.day,
        meal=event.meal,
        status=event.status,
        servings=event.servings,
        actor=event.actor,
        reason=event.reason,
        recipe_title=event.recipe_title,
        nutrition_payload=event.nutrition_payload,
        override_payload=event.override_payload,
        consumed_at=event.consumed_at,
        created_at=_iso(event.created_at),
    )


def consumption_record_response(event: ConsumptionEvent) -> ConsumptionRecordResponse:
    return ConsumptionRecordResponse(
        event=consumption_event_response(event),
        assistant_boundary=(
            "Consumption events are self-reported user facts. They estimate nutrition from the accepted plan "
            "or explicit user override and do not replace medical or dietary advice."
        ),
    )


async def _get_accepted_plan(
    session: AsyncSession,
    *,
    household_id: str,
    accepted_plan_id: str,
) -> AcceptedPlan:
    result = await session.execute(
        select(AcceptedPlan).where(
            AcceptedPlan.household_id == household_id,
            AcceptedPlan.id == accepted_plan_id,
        )
    )
    plan = result.scalar_one_or_none()
    if plan is None:
        raise LookupError("Accepted plan not found")
    return plan


def _meal_payload(plan: AcceptedPlan, day: int, meal: str) -> dict[str, Any]:
    days = (plan.plan_payload or {}).get("days") or []
    day_payload = next((item for item in days if int(item.get("day", -1)) == day), None)
    if not day_payload:
        raise ValueError("Day not found in accepted plan")
    meals = day_payload.get("meals") or {}
    meal_payload = meals.get(meal)
    if not meal_payload:
        raise ValueError("Meal not found in accepted plan")
    return meal_payload


def _normalize_nutrition(raw: dict[str, Any], servings: float) -> dict[str, float]:
    return {
        "calories": round(_safe_float(raw.get("calories")) * servings, 1),
        "protein_g": round(_safe_float(raw.get("protein_g", raw.get("protein"))) * servings, 1),
        "carbs_g": round(_safe_float(raw.get("carbs_g", raw.get("carbs"))) * servings, 1),
        "fats_g": round(_safe_float(raw.get("fats_g", raw.get("fats"))) * servings, 1),
    }


def _nutrition_payload(
    *,
    meal_payload: dict[str, Any],
    request: ConsumptionEventCreateRequest,
) -> dict[str, Any]:
    if request.status == "skipped":
        return {"calories": 0, "protein_g": 0, "carbs_g": 0, "fats_g": 0}
    if request.nutrition_payload:
        return request.nutrition_payload
    recipe = meal_payload.get("recipe") or {}
    return _normalize_nutrition(recipe.get("nutrition") or {}, request.servings)


async def record_consumption_event(
    session: AsyncSession,
    *,
    household_id: str,
    request: ConsumptionEventCreateRequest,
) -> ConsumptionEvent:
    if request.status == "changed" and not request.override_payload:
        raise ValueError("override_payload is required for changed consumption events")

    plan = await _get_accepted_plan(
        session,
        household_id=household_id,
        accepted_plan_id=request.accepted_plan_id,
    )
    meal_payload = _meal_payload(plan, request.day, request.meal)
    recipe = meal_payload.get("recipe") or {}
    nutrition_payload = _nutrition_payload(meal_payload=meal_payload, request=request)
    consumed_at = request.consumed_at or now_utc().isoformat(timespec="seconds")

    event = ConsumptionEvent(
        household_id=household_id,
        accepted_plan_id=request.accepted_plan_id,
        day=request.day,
        meal=request.meal,
        status=request.status,
        servings=request.servings,
        actor=request.actor,
        reason=request.reason,
        recipe_title=recipe.get("title"),
        nutrition_payload=nutrition_payload,
        override_payload=request.override_payload,
        consumed_at=consumed_at,
    )
    session.add(event)
    await session.flush()
    await create_audit_event(
        session,
        household_id=household_id,
        event_type=f"meal_{request.status}",
        actor=request.actor,
        object_type="consumption_event",
        object_id=event.id,
        reason=request.reason,
        payload={
            "consumption_event_id": event.id,
            "accepted_plan_id": request.accepted_plan_id,
            "day": request.day,
            "meal": request.meal,
            "status": request.status,
            "recipe_title": event.recipe_title,
            "nutrition_payload": nutrition_payload,
        },
    )
    await session.commit()
    return event


async def list_consumption_events(
    session: AsyncSession,
    household_id: str,
    *,
    accepted_plan_id: str | None = None,
    limit: int = 50,
) -> list[ConsumptionEvent]:
    query = select(ConsumptionEvent).where(ConsumptionEvent.household_id == household_id)
    if accepted_plan_id:
        query = query.where(ConsumptionEvent.accepted_plan_id == accepted_plan_id)
    result = await session.execute(
        query.order_by(ConsumptionEvent.created_at.desc(), ConsumptionEvent.id.desc()).limit(limit)
    )
    return list(result.scalars())
