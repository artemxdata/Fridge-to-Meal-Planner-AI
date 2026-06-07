from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_demo_household_seeds_confirmed_pantry_and_audit_events() -> None:
    household = client.get("/api/v3/households/demo")

    assert household.status_code == 200
    household_id = household.json()["id"]

    pantry = client.get(f"/api/v3/households/{household_id}/pantry")
    audit = client.get(f"/api/v3/households/{household_id}/audit-events")

    assert pantry.status_code == 200
    assert len(pantry.json()) >= 6
    assert all(item["status"] == "confirmed" for item in pantry.json())
    assert audit.status_code == 200
    assert any(event["event_type"] == "pantry_items_confirmed" for event in audit.json())


def test_confirm_pantry_items_creates_lots_and_audit_event() -> None:
    household_id = client.get("/api/v3/households/demo").json()["id"]
    response = client.post(
        f"/api/v3/households/{household_id}/pantry/confirm",
        json={
            "actor": "test-user",
            "reason": "test confirmed candidates",
            "items": [
                {
                    "name": "помидор",
                    "quantity": 2,
                    "unit": "шт",
                    "source": "manual_test",
                    "confidence": 1,
                }
            ],
        },
    )

    assert response.status_code == 200
    created = response.json()
    assert len(created) == 1
    assert created[0]["ingredient_name"] == "помидор"

    audit = client.get(f"/api/v3/households/{household_id}/audit-events").json()
    assert any(
        event["event_type"] == "pantry_items_confirmed"
        and event["actor"] == "test-user"
        and "помидор" in event["payload"]["ingredient_names"]
        for event in audit
    )


def _draft_plan_option() -> dict:
    demo = client.get("/api/v2/demo").json()
    response = client.post(
        "/api/v3/plans/options",
        json={
            "pantry": demo["pantry"],
            "budget_per_day": 520,
            "target_calories": 1800,
            "protein_goal_g": 95,
            "days": 3,
        },
    )

    assert response.status_code == 200
    return response.json()["options"][0]


def test_approve_plan_option_creates_approval_and_audit_events() -> None:
    household_id = client.get("/api/v3/households/demo").json()["id"]
    option = _draft_plan_option()

    response = client.post(
        f"/api/v3/households/{household_id}/plans/approve",
        json={
            "actor": "test-user",
            "reason": "approved after reviewing draft",
            "option": option,
        },
    )

    assert response.status_code == 200
    event = response.json()
    assert event["event_type"] == "plan_option_approved"
    assert event["status"] == "approved"
    assert event["target_id"] == option["option_id"]
    assert event["approved_payload"]["shopping_list"] == option["plan"]["shopping_list"]

    approval_events = client.get(f"/api/v3/households/{household_id}/approval-events").json()
    assert any(item["id"] == event["id"] for item in approval_events)

    audit = client.get(f"/api/v3/households/{household_id}/audit-events").json()
    assert any(
        item["event_type"] == "plan_option_approved" and item["object_id"] == event["id"] for item in audit
    )


def test_override_plan_option_requires_reason_and_payload() -> None:
    household_id = client.get("/api/v3/households/demo").json()["id"]
    option = _draft_plan_option()

    empty_override = client.post(
        f"/api/v3/households/{household_id}/plans/override",
        json={
            "actor": "test-user",
            "reason": "replace dinner",
            "original_option": option,
            "override_payload": {},
        },
    )
    assert empty_override.status_code == 422

    response = client.post(
        f"/api/v3/households/{household_id}/plans/override",
        json={
            "actor": "test-user",
            "reason": "replace dinner with a faster meal",
            "original_option": option,
            "override_payload": {
                "day": "day_1",
                "meal": "dinner",
                "replacement": "omelet",
            },
        },
    )

    assert response.status_code == 200
    event = response.json()
    assert event["event_type"] == "plan_option_overridden"
    assert event["status"] == "overridden"
    assert event["target_id"] == option["option_id"]
    assert event["override_payload"]["replacement"] == "omelet"


def test_unknown_household_returns_404() -> None:
    pantry = client.get("/api/v3/households/unknown-household/pantry")
    confirm = client.post(
        "/api/v3/households/unknown-household/pantry/confirm",
        json={"items": [{"name": "яйца", "quantity": 1}]},
    )

    assert pantry.status_code == 404
    assert confirm.status_code == 404


def test_unknown_household_returns_404_for_plan_decisions() -> None:
    option = _draft_plan_option()
    approval_events = client.get("/api/v3/households/unknown-household/approval-events")
    approve = client.post(
        "/api/v3/households/unknown-household/plans/approve",
        json={"option": option},
    )
    override = client.post(
        "/api/v3/households/unknown-household/plans/override",
        json={
            "original_option": option,
            "reason": "replace meal",
            "override_payload": {"replacement": "omelet"},
        },
    )

    assert approval_events.status_code == 404
    assert approve.status_code == 404
    assert override.status_code == 404
