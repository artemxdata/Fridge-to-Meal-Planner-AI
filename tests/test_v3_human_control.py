from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_context_interpretation_is_transparent_and_requires_confirmation() -> None:
    response = client.post(
        "/api/v3/assistant/interpret-context",
        json={"text": "Я устал, хочу что-то тёплое без магазина и с минимумом посуды"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["requires_confirmation"] is True
    assert data["proposed_constraints"]["shopping_allowed"] is False
    assert data["proposed_constraints"]["cleanup_level"] == "low"
    assert data["proposed_constraints"]["meal_mood"] == "comfort"
    assert data["evidence"]


def test_plan_options_are_explainable_drafts() -> None:
    demo = client.get("/api/v2/demo").json()
    response = client.post(
        "/api/v3/plans/options",
        json={
            "pantry": demo["pantry"],
            "budget_per_day": 520,
            "target_calories": 1800,
            "protein_goal_g": 95,
            "days": 3,
            "context_note": "Сегодня мало сил",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert {option["strategy"] for option in data["options"]} == {"simple", "waste_first", "balanced"}
    assert all(option["requires_approval"] for option in data["options"])
    assert all(option["approval_status"] == "draft" for option in data["options"])
    assert all(option["decision_trace"] for option in data["options"])
    assert all(len(option["plan"]["days"]) == 3 for option in data["options"])


def test_companion_state_is_explainable_and_non_authoritative() -> None:
    demo = client.get("/api/v2/demo").json()
    options = client.post(
        "/api/v3/plans/options",
        json={
            "pantry": demo["pantry"],
            "budget_per_day": 520,
            "target_calories": 1800,
            "protein_goal_g": 95,
            "days": 3,
        },
    ).json()["options"]
    plan = next(option["plan"] for option in options if option["strategy"] == "balanced")

    response = client.post(
        "/api/v3/companion/state",
        json={
            "plan": plan,
            "pantry": demo["pantry"],
            "budget_per_day": 520,
            "protein_goal_g": 95,
            "days": 3,
            "mascot": "nerpa",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["mascot"] == "nerpa"
    assert 0 <= data["score"] <= 100
    assert {signal["key"] for signal in data["signals"]} == {
        "protein",
        "budget",
        "pantry_usage",
        "waste_risk",
        "shopping_load",
    }
    assert "does not judge the user" in data["assistant_boundary"]


def test_v3_plan_options_respect_requested_horizon() -> None:
    response = client.post(
        "/api/v3/plans/options",
        json={
            "pantry": [{"name": "яйца", "quantity": 4}],
            "budget_per_day": 500,
            "days": 1,
        },
    )

    assert response.status_code == 200
    assert all(len(option["plan"]["days"]) == 1 for option in response.json()["options"])


def test_policy_constraints_exclude_allergy_ingredients() -> None:
    demo = client.get("/api/v2/demo").json()
    response = client.post(
        "/api/v3/plans/options",
        json={
            "pantry": demo["pantry"],
            "budget_per_day": 520,
            "days": 1,
            "policy": {
                "allergies": ["яйца"],
                "low_dishes": True,
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert all(
        "яйца" not in recipe["recipe"]["ingredients"]
        for option in data["options"]
        for day in option["plan"]["days"]
        for recipe in day["meals"].values()
    )
    assert all(
        any(trace["rule"] == "policy_constraints_applied" for trace in option["decision_trace"])
        for option in data["options"]
    )


def test_no_shop_policy_can_build_plan_without_shopping_list() -> None:
    pantry = [
        {"name": "овсянка", "quantity": 2},
        {"name": "йогурт", "quantity": 2},
        {"name": "яблоко", "quantity": 2},
        {"name": "мёд", "quantity": 2},
        {"name": "помидор", "quantity": 4},
        {"name": "огурец", "quantity": 2},
        {"name": "сыр", "quantity": 2},
        {"name": "маслины", "quantity": 2},
        {"name": "масло растительное", "quantity": 2},
        {"name": "паста", "quantity": 2},
        {"name": "чеснок", "quantity": 2},
    ]
    response = client.post(
        "/api/v3/plans/options",
        json={
            "pantry": pantry,
            "budget_per_day": 520,
            "days": 1,
            "policy": {
                "no_shop_mode": True,
                "strict_budget": True,
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert all(option["plan"]["shopping_list"] == [] for option in data["options"])
    assert all(option["plan"]["policy"]["no_shop_mode"] is True for option in data["options"])


def test_impossible_policy_returns_422() -> None:
    response = client.post(
        "/api/v3/plans/options",
        json={
            "pantry": [{"name": "яйца", "quantity": 1}],
            "budget_per_day": 500,
            "days": 1,
            "policy": {"max_cooking_time_min": 1},
        },
    )

    assert response.status_code == 422
