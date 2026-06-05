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
