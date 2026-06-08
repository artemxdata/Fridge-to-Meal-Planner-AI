from __future__ import annotations

from typing import Any

from app.schemas import (
    CompanionSignal,
    CompanionStateRequest,
    CompanionStateResponse,
    PantryItem,
)

DISPLAY_NAMES = {
    "nerpa": "Nerpa companion",
    "sunflower": "Sunflower companion",
    "kitchen_helper": "Kitchen helper",
}


def _status(score: int, action_threshold: int = 45, watch_threshold: int = 72) -> str:
    if score < action_threshold:
        return "action"
    if score < watch_threshold:
        return "watch"
    return "good"


def _percent(value: float) -> str:
    return f"{round(value * 100)}%"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _expiring_count(pantry: list[PantryItem]) -> int:
    return sum(1 for item in pantry if item.expires_in_days is not None and item.expires_in_days <= 3)


def _signal(
    key: str,
    label: str,
    value: str,
    status: str,
    explanation: str,
    source: str,
) -> CompanionSignal:
    return CompanionSignal(
        key=key,
        label=label,
        value=value,
        status=status,
        explanation=explanation,
        source=source,
    )


def build_companion_state(request: CompanionStateRequest) -> CompanionStateResponse:
    plan = request.plan or {}
    totals = plan.get("totals") or {}
    statistics = plan.get("statistics") or {}
    shopping_list = plan.get("shopping_list") or []

    days = max(1, request.days)
    protein_goal = max(0, request.protein_goal_g or 0) * days
    protein = _safe_float(totals.get("protein_g"))
    protein_ratio = 1.0 if protein_goal == 0 else min(1.2, protein / protein_goal)
    protein_score = int(min(100, protein_ratio * 100))

    budget_limit = _safe_float(totals.get("budget_limit"), request.budget_per_day * days)
    if budget_limit <= 0:
        budget_limit = request.budget_per_day * days
    cost = _safe_float(totals.get("cost"))
    budget_ratio = cost / budget_limit if budget_limit else 0
    budget_score = 100 if budget_ratio <= 1 else max(0, int(100 - (budget_ratio - 1) * 180))

    pantry_usage = _safe_float(statistics.get("pantry_usage_percent"))
    pantry_score = int(min(100, max(0, pantry_usage)))

    expiring_count = _expiring_count(request.pantry)
    waste_score = 100 if expiring_count == 0 else max(25, 100 - expiring_count * 18)

    shopping_count = len(shopping_list)
    shopping_score = max(20, 100 - shopping_count * 8)

    signals = [
        _signal(
            "protein",
            "Protein target",
            f"{round(protein, 1)}g / {protein_goal}g",
            _status(protein_score),
            "Reflects whether the current draft is close to the explicit protein target.",
            "plan.totals.protein_g",
        ),
        _signal(
            "budget",
            "Budget fit",
            f"{round(cost, 2)} / {round(budget_limit, 2)}",
            _status(budget_score),
            "Compares estimated plan cost with the confirmed budget limit.",
            "plan.totals.cost",
        ),
        _signal(
            "pantry_usage",
            "Pantry usage",
            _percent(pantry_usage / 100),
            _status(pantry_score, action_threshold=25, watch_threshold=55),
            "Shows how much of the confirmed pantry appears in the draft recipes.",
            "plan.statistics.pantry_usage_percent",
        ),
        _signal(
            "waste_risk",
            "Use-soon items",
            str(expiring_count),
            _status(waste_score),
            "Counts confirmed pantry items with three or fewer days left.",
            "confirmed_pantry.expires_in_days",
        ),
        _signal(
            "shopping_load",
            "Shopping load",
            str(shopping_count),
            _status(shopping_score),
            "Estimates how much extra buying the accepted draft would require.",
            "plan.shopping_list",
        ),
    ]

    score = int(
        round(
            protein_score * 0.28
            + budget_score * 0.24
            + pantry_score * 0.18
            + waste_score * 0.16
            + shopping_score * 0.14
        )
    )

    priority = sorted(
        signals,
        key=lambda item: ({"action": 0, "watch": 1, "good": 2}[item.status], item.key),
    )[0]
    state = {
        "protein": "needs_protein",
        "budget": "budget_watch",
        "pantry_usage": "shopping_heavy",
        "waste_risk": "use_soon",
        "shopping_load": "shopping_heavy",
    }.get(priority.key, "steady")
    if score < 45 and priority.status == "action":
        state = "overloaded"
    if all(signal.status == "good" for signal in signals):
        state = "steady"

    messages = {
        "steady": "The draft looks balanced enough to review calmly.",
        "needs_protein": "Protein is the clearest gap; add or swap one protein source before approval.",
        "budget_watch": "Budget needs attention; review expensive meals before approval.",
        "use_soon": "Some confirmed pantry items should be used soon.",
        "shopping_heavy": "The draft may create too much shopping work.",
        "overloaded": "Several signals need review before this draft becomes an accepted plan.",
    }
    visual_hints = {
        "steady": "upright with a calm checklist",
        "needs_protein": "holding a protein reminder card",
        "budget_watch": "checking a small budget clipboard",
        "use_soon": "pointing at a use-soon shelf",
        "shopping_heavy": "standing beside a heavy shopping bag",
        "overloaded": "resting next to stacked decision notes",
    }

    return CompanionStateResponse(
        mascot=request.mascot,
        state=state,
        display_name=DISPLAY_NAMES[request.mascot],
        score=max(0, min(100, score)),
        message=messages[state],
        visual_hint=visual_hints[state],
        signals=signals,
        assistant_boundary=(
            "The companion reflects explainable plan signals only. It does not judge the user, "
            "change pantry facts, approve plans, or make autonomous health decisions."
        ),
    )
