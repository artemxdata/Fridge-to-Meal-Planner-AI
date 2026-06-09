from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AcceptedPlan, ConsumptionEvent, PantryLot, PurchaseEvent
from app.schemas import HouseholdSummaryReportResponse, ReportMetric


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _status_from_ratio(ratio: float, *, good: float, action: float) -> str:
    if ratio >= good:
        return "good"
    if ratio < action:
        return "action"
    return "watch"


async def _latest_accepted_plan(session: AsyncSession, household_id: str) -> AcceptedPlan | None:
    result = await session.execute(
        select(AcceptedPlan)
        .where(AcceptedPlan.household_id == household_id, AcceptedPlan.status == "active")
        .order_by(AcceptedPlan.created_at.desc(), AcceptedPlan.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _purchase_events_for_plan(
    session: AsyncSession,
    household_id: str,
    accepted_plan_id: str | None,
) -> list[PurchaseEvent]:
    query = select(PurchaseEvent).where(PurchaseEvent.household_id == household_id)
    if accepted_plan_id:
        query = query.where(PurchaseEvent.accepted_plan_id == accepted_plan_id)
    result = await session.execute(query.order_by(PurchaseEvent.created_at.desc(), PurchaseEvent.id.desc()))
    return list(result.scalars())


async def _consumption_events_for_plan(
    session: AsyncSession,
    household_id: str,
    accepted_plan_id: str | None,
) -> list[ConsumptionEvent]:
    query = select(ConsumptionEvent).where(ConsumptionEvent.household_id == household_id)
    if accepted_plan_id:
        query = query.where(ConsumptionEvent.accepted_plan_id == accepted_plan_id)
    result = await session.execute(
        query.order_by(ConsumptionEvent.created_at.desc(), ConsumptionEvent.id.desc())
    )
    return list(result.scalars())


async def _pantry_lots_count(session: AsyncSession, household_id: str) -> int:
    result = await session.execute(select(PantryLot.id).where(PantryLot.household_id == household_id))
    return len(result.scalars().all())


def _plan_metrics(
    plan: AcceptedPlan | None,
    *,
    period_days: int,
    protein_goal_g: int,
    budget_per_day: float,
) -> tuple[list[ReportMetric], list[str], dict[str, Any]]:
    if plan is None:
        return (
            [
                ReportMetric(
                    key="accepted_plan",
                    label="Accepted plan",
                    value="missing",
                    status="action",
                    source="accepted_plans",
                    explanation="No user-approved plan is active for this household yet.",
                )
            ],
            ["Approve a draft plan before treating nutrition, budget, or shopping numbers as actionable."],
            {"accepted_plan_id": None, "option_id": None},
        )

    payload = plan.plan_payload or {}
    totals = payload.get("totals") or {}
    statistics = payload.get("statistics") or {}
    shopping_list = payload.get("shopping_list") or []
    planned_protein = _safe_float(totals.get("protein_g"))
    planned_cost = _safe_float(totals.get("cost"))
    budget_limit = _safe_float(totals.get("budget_limit"), budget_per_day * period_days)
    protein_goal_total = max(0, protein_goal_g) * period_days
    protein_ratio = 1.0 if protein_goal_total == 0 else planned_protein / protein_goal_total
    cost_ratio = planned_cost / budget_limit if budget_limit > 0 else 0
    pantry_usage = _safe_float(statistics.get("pantry_usage_percent"))

    insights = []
    if protein_ratio < 0.8:
        insights.append("Planned protein is below target; review breakfast or snack protein before approval.")
    if cost_ratio > 1:
        insights.append("Accepted plan is above the budget target; review high-cost meals or shopping items.")
    if shopping_list:
        insights.append("Shopping list still has missing ingredients; record purchases after shopping.")
    if pantry_usage >= 60:
        insights.append("Plan uses a meaningful share of existing pantry items.")

    return (
        [
            ReportMetric(
                key="planned_protein",
                label="Planned protein",
                value=round(planned_protein, 1),
                unit="g",
                status=_status_from_ratio(protein_ratio, good=0.95, action=0.8),
                source="accepted_plans.plan_payload.totals.protein_g",
                explanation="Compares accepted plan protein with the report protein target.",
            ),
            ReportMetric(
                key="protein_goal_coverage",
                label="Protein goal coverage",
                value=round(protein_ratio * 100, 1),
                unit="%",
                status=_status_from_ratio(protein_ratio, good=0.95, action=0.8),
                source="accepted_plans + report parameters",
                explanation="Shows how much of the requested protein target the accepted plan covers.",
            ),
            ReportMetric(
                key="planned_cost",
                label="Planned cost",
                value=round(planned_cost, 2),
                unit="RUB",
                status="good" if cost_ratio <= 1 else "watch",
                source="accepted_plans.plan_payload.totals.cost",
                explanation="Estimated cost from the accepted plan.",
            ),
            ReportMetric(
                key="budget_usage",
                label="Budget usage",
                value=round(cost_ratio * 100, 1) if budget_limit else 0,
                unit="%",
                status="good" if cost_ratio <= 1 else "watch",
                source="accepted_plans + report parameters",
                explanation="Compares estimated plan cost with the report budget target.",
            ),
            ReportMetric(
                key="pantry_usage",
                label="Pantry usage",
                value=round(pantry_usage, 1),
                unit="%",
                status="good" if pantry_usage >= 60 else "watch",
                source="accepted_plans.plan_payload.statistics.pantry_usage_percent",
                explanation="Share of known pantry ingredients used by the accepted plan.",
            ),
            ReportMetric(
                key="shopping_items",
                label="Shopping items",
                value=len(shopping_list),
                unit="items",
                status="good" if not shopping_list else "watch",
                source="accepted_plans.shopping_list_payload",
                explanation="Number of missing ingredients in the accepted plan shopping list.",
            ),
        ],
        insights,
        {
            "accepted_plan_id": plan.id,
            "option_id": plan.option_id,
            "strategy": plan.strategy,
            "protein_goal_total_g": protein_goal_total,
            "budget_limit": round(budget_limit, 2),
        },
    )


def _purchase_metrics(purchases: list[PurchaseEvent]) -> tuple[list[ReportMetric], list[str], dict[str, Any]]:
    total_cost = round(sum(_safe_float(event.total_cost) for event in purchases), 2)
    items_count = sum(len(event.items_payload or []) for event in purchases)
    pantry_lots_count = sum(len(event.pantry_lot_ids or []) for event in purchases)
    currencies = sorted({event.currency for event in purchases if event.currency})
    currency = currencies[0] if len(currencies) == 1 else None

    insights = []
    if purchases:
        insights.append("Purchase history is linked back to pantry lots, so shopping results are auditable.")

    return (
        [
            ReportMetric(
                key="purchase_events",
                label="Purchase events",
                value=len(purchases),
                unit="events",
                status="neutral",
                source="purchase_events",
                explanation="Number of user-confirmed purchase records in this report scope.",
            ),
            ReportMetric(
                key="purchased_items",
                label="Purchased items",
                value=items_count,
                unit="items",
                status="neutral",
                source="purchase_events.items_payload",
                explanation="Total number of item rows recorded through purchase events.",
            ),
            ReportMetric(
                key="purchase_total_cost",
                label="Purchase total cost",
                value=total_cost,
                unit=currency,
                status="neutral",
                source="purchase_events.total_cost",
                explanation="Sum of recorded purchase costs where users provided a total.",
            ),
            ReportMetric(
                key="purchase_pantry_lots",
                label="Pantry lots from purchases",
                value=pantry_lots_count,
                unit="lots",
                status="neutral",
                source="purchase_events.pantry_lot_ids",
                explanation="Confirmed pantry lots created from purchase records.",
            ),
        ],
        insights,
        {"purchase_event_ids": [event.id for event in purchases], "purchase_currency": currency},
    )


def _nutrition_value(event: ConsumptionEvent, key: str, fallback_key: str | None = None) -> float:
    payload = event.nutrition_payload or {}
    return _safe_float(payload.get(key, payload.get(fallback_key or key)))


def _consumption_metrics(
    consumptions: list[ConsumptionEvent],
    *,
    period_days: int,
    protein_goal_g: int,
) -> tuple[list[ReportMetric], list[str], dict[str, Any]]:
    logged_count = len(consumptions)
    skipped_count = sum(1 for event in consumptions if event.status == "skipped")
    changed_count = sum(1 for event in consumptions if event.status == "changed")
    consumed_like = [event for event in consumptions if event.status in {"consumed", "changed"}]
    actual_protein = round(sum(_nutrition_value(event, "protein_g", "protein") for event in consumed_like), 1)
    actual_calories = round(sum(_nutrition_value(event, "calories") for event in consumed_like), 1)
    protein_goal_total = max(0, protein_goal_g) * period_days
    protein_ratio = 1.0 if protein_goal_total == 0 else actual_protein / protein_goal_total

    insights = []
    if not consumptions:
        insights.append(
            "No consumption events yet; actual nutrition remains unknown until the user logs meals."
        )
    elif protein_ratio < 0.8:
        insights.append("Logged protein is below target; this is based only on self-reported consumed meals.")
    if skipped_count:
        insights.append("Some accepted meals were skipped; future planning can use this as feedback.")
    if changed_count:
        insights.append("Some meals were changed by the user; overrides can become ranking feedback later.")

    protein_status = (
        "neutral" if not consumptions else _status_from_ratio(protein_ratio, good=0.95, action=0.8)
    )

    return (
        [
            ReportMetric(
                key="actual_protein",
                label="Actual logged protein",
                value=actual_protein,
                unit="g",
                status=protein_status,
                source="consumption_events.nutrition_payload.protein_g",
                explanation="Protein from self-reported consumed or changed meals.",
            ),
            ReportMetric(
                key="actual_protein_goal_coverage",
                label="Actual protein coverage",
                value=round(protein_ratio * 100, 1) if consumptions else 0,
                unit="%",
                status=protein_status,
                source="consumption_events + report parameters",
                explanation="Compares logged protein with the report protein target.",
            ),
            ReportMetric(
                key="actual_calories",
                label="Actual logged calories",
                value=actual_calories,
                unit="kcal",
                status="neutral",
                source="consumption_events.nutrition_payload.calories",
                explanation="Calories from self-reported consumed or changed meals.",
            ),
            ReportMetric(
                key="logged_meals",
                label="Logged meals",
                value=logged_count,
                unit="events",
                status="good" if logged_count else "watch",
                source="consumption_events",
                explanation="Number of meal consumption decisions recorded by the user.",
            ),
            ReportMetric(
                key="skipped_meals",
                label="Skipped meals",
                value=skipped_count,
                unit="events",
                status="watch" if skipped_count else "good",
                source="consumption_events.status",
                explanation="Accepted meals the user explicitly marked as skipped.",
            ),
            ReportMetric(
                key="changed_meals",
                label="Changed meals",
                value=changed_count,
                unit="events",
                status="watch" if changed_count else "good",
                source="consumption_events.status",
                explanation="Accepted meals the user changed before logging consumption.",
            ),
        ],
        insights,
        {"consumption_event_ids": [event.id for event in consumptions]},
    )


async def build_household_summary_report(
    session: AsyncSession,
    *,
    household_id: str,
    period_days: int,
    protein_goal_g: int,
    budget_per_day: float,
) -> HouseholdSummaryReportResponse:
    plan = await _latest_accepted_plan(session, household_id)
    plan_metrics, plan_insights, plan_sources = _plan_metrics(
        plan,
        period_days=period_days,
        protein_goal_g=protein_goal_g,
        budget_per_day=budget_per_day,
    )
    purchases = await _purchase_events_for_plan(session, household_id, plan.id if plan else None)
    purchase_metrics, purchase_insights, purchase_sources = _purchase_metrics(purchases)
    consumptions = await _consumption_events_for_plan(session, household_id, plan.id if plan else None)
    consumption_metrics, consumption_insights, consumption_sources = _consumption_metrics(
        consumptions,
        period_days=period_days,
        protein_goal_g=protein_goal_g,
    )
    pantry_lots_count = await _pantry_lots_count(session, household_id)

    return HouseholdSummaryReportResponse(
        household_id=household_id,
        period_days=period_days,
        has_accepted_plan=plan is not None,
        accepted_plan_id=plan.id if plan else None,
        generated_from={
            **plan_sources,
            **purchase_sources,
            **consumption_sources,
            "pantry_lots_count": pantry_lots_count,
            "report_parameters": {
                "period_days": period_days,
                "protein_goal_g": protein_goal_g,
                "budget_per_day": budget_per_day,
            },
        },
        metrics=[
            *plan_metrics,
            *purchase_metrics,
            *consumption_metrics,
            ReportMetric(
                key="current_pantry_lots",
                label="Current pantry lots",
                value=pantry_lots_count,
                unit="lots",
                status="neutral",
                source="pantry_lots",
                explanation="Number of confirmed pantry lots currently stored for this household.",
            ),
        ],
        insights=plan_insights + purchase_insights + consumption_insights,
        assistant_boundary=(
            "This report is computed from confirmed pantry, approved plans, user-recorded purchases, "
            "and self-reported consumption events. It is not a medical diagnosis."
        ),
    )
