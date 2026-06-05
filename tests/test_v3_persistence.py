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


def test_unknown_household_returns_404() -> None:
    pantry = client.get("/api/v3/households/unknown-household/pantry")
    confirm = client.post(
        "/api/v3/households/unknown-household/pantry/confirm",
        json={"items": [{"name": "яйца", "quantity": 1}]},
    )

    assert pantry.status_code == 404
    assert confirm.status_code == 404
