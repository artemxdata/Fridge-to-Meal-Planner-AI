import asyncio
import uuid

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import Household

client = TestClient(app)


def _create_test_household(household_id: str) -> None:
    async def create() -> None:
        async with SessionLocal() as session:
            if await session.get(Household, household_id) is None:
                session.add(Household(id=household_id, name=f"Test household {household_id}", locale="ru"))
                await session.commit()

    asyncio.run(create())


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


def test_observation_candidates_require_confirmation_before_pantry() -> None:
    household_id = client.get("/api/v3/households/demo").json()["id"]
    create = client.post(
        f"/api/v3/households/{household_id}/observations",
        json={
            "source": "receipt",
            "actor": "test-user",
            "reason": "stored parsed receipt candidates",
            "raw_payload": {"fallback": "receipt_barcode_heuristics"},
            "candidates": [
                {
                    "name": "йогурт",
                    "quantity": 2,
                    "unit": "шт",
                    "confidence": 0.78,
                    "source": "receipt_text",
                    "reason": "matched product name",
                },
                {
                    "name": "молоко",
                    "quantity": 1,
                    "unit": "шт",
                    "confidence": 0.92,
                    "source": "barcode_demo_catalog",
                    "reason": "matched demo barcode",
                },
            ],
        },
    )

    assert create.status_code == 200
    observation = create.json()
    assert observation["status"] == "pending"
    assert observation["needs_confirmation"] is True
    assert len(observation["candidates"]) == 2
    assert all(candidate["status"] == "pending" for candidate in observation["candidates"])

    candidate_id = observation["candidates"][0]["id"]
    confirm = client.post(
        f"/api/v3/households/{household_id}/observations/{observation['id']}/confirm",
        json={
            "actor": "test-user",
            "reason": "confirmed one candidate after review",
            "candidates": [
                {
                    "candidate_id": candidate_id,
                    "item": {
                        "name": "йогурт греческий",
                        "quantity": 1,
                        "unit": "шт",
                        "source": "human_confirmed_observation",
                        "confidence": 0.9,
                    },
                }
            ],
        },
    )

    assert confirm.status_code == 200
    confirmed = confirm.json()
    assert confirmed["status"] == "partially_confirmed"
    confirmed_candidate = next(item for item in confirmed["candidates"] if item["id"] == candidate_id)
    assert confirmed_candidate["status"] == "confirmed"
    assert confirmed_candidate["display_name"] == "йогурт греческий"

    pantry = client.get(f"/api/v3/households/{household_id}/pantry").json()
    assert any(item["display_name"] == "йогурт греческий" for item in pantry)

    observations = client.get(f"/api/v3/households/{household_id}/observations").json()
    assert any(item["id"] == observation["id"] for item in observations)

    audit = client.get(f"/api/v3/households/{household_id}/audit-events").json()
    assert any(event["event_type"] == "observation_session_created" for event in audit)
    assert any(event["event_type"] == "observation_candidates_confirmed" for event in audit)


def test_observation_confirmation_is_scoped_to_household() -> None:
    household_id = client.get("/api/v3/households/demo").json()["id"]
    other_household_id = f"test-household-{uuid.uuid4()}"
    _create_test_household(other_household_id)
    create = client.post(
        f"/api/v3/households/{household_id}/observations",
        json={
            "source": "manual",
            "actor": "test-user",
            "reason": "stored candidate for scope test",
            "candidates": [
                {
                    "name": "eggs",
                    "quantity": 1,
                    "confidence": 0.7,
                    "source": "manual",
                    "reason": "scope test candidate",
                }
            ],
        },
    )

    assert create.status_code == 200
    observation = create.json()
    candidate_id = observation["candidates"][0]["id"]

    cross_household_confirm = client.post(
        f"/api/v3/households/{other_household_id}/observations/{observation['id']}/confirm",
        json={
            "actor": "test-user",
            "reason": "attempted cross-household confirmation",
            "candidates": [
                {
                    "candidate_id": candidate_id,
                    "item": {"name": "eggs", "quantity": 1},
                }
            ],
        },
    )

    assert cross_household_confirm.status_code == 404
    assert cross_household_confirm.json()["detail"] == "Observation session not found"


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
    assert event["approved_payload"]["accepted_plan_id"]

    accepted = client.get(f"/api/v3/households/{household_id}/plans/accepted/latest")
    assert accepted.status_code == 200
    accepted_plan = accepted.json()
    assert accepted_plan["id"] == event["approved_payload"]["accepted_plan_id"]
    assert accepted_plan["option_id"] == option["option_id"]
    assert accepted_plan["shopping_list_payload"] == option["plan"]["shopping_list"]

    approval_events = client.get(f"/api/v3/households/{household_id}/approval-events").json()
    assert any(item["id"] == event["id"] for item in approval_events)

    audit = client.get(f"/api/v3/households/{household_id}/audit-events").json()
    assert any(
        item["event_type"] == "plan_option_approved" and item["object_id"] == event["id"] for item in audit
    )


def test_consent_events_are_append_only_and_current_state_uses_latest_decision() -> None:
    household_id = client.get("/api/v3/households/demo").json()["id"]
    consent_payload = {
        "consent_type": "model_training",
        "status": "granted",
        "scope": "photo_feedback_dataset",
        "actor": "test-user",
        "reason": "opted in after reading privacy notice",
        "policy_version": "privacy-v1",
        "source": "test",
        "payload": {"surface": "settings"},
    }

    grant = client.post(f"/api/v3/households/{household_id}/consent-events", json=consent_payload)
    revoke = client.post(
        f"/api/v3/households/{household_id}/consent-events",
        json={
            **consent_payload,
            "status": "revoked",
            "reason": "changed mind after review",
        },
    )

    assert grant.status_code == 200
    assert revoke.status_code == 200
    assert grant.json()["status"] == "granted"
    assert revoke.json()["status"] == "revoked"

    history = client.get(f"/api/v3/households/{household_id}/consent-events").json()
    history_ids = {event["id"] for event in history}
    assert {grant.json()["id"], revoke.json()["id"]} <= history_ids

    current = client.get(f"/api/v3/households/{household_id}/consents/current")
    assert current.status_code == 200
    current_items = current.json()["consents"]
    current_training = next(
        item
        for item in current_items
        if item["consent_type"] == "model_training" and item["scope"] == "photo_feedback_dataset"
    )
    assert current_training["id"] == revoke.json()["id"]
    assert current_training["status"] == "revoked"
    assert "append-only" in current.json()["assistant_boundary"]

    audit = client.get(f"/api/v3/households/{household_id}/audit-events").json()
    assert any(
        event["event_type"] == "consent_granted" and event["object_id"] == grant.json()["id"]
        for event in audit
    )
    assert any(
        event["event_type"] == "consent_revoked" and event["object_id"] == revoke.json()["id"]
        for event in audit
    )


def test_latest_accepted_plan_returns_current_active_approval() -> None:
    household_id = client.get("/api/v3/households/demo").json()["id"]
    first_option = _draft_plan_option()
    second_option = {**_draft_plan_option(), "option_id": "second-option", "title": "Second option"}

    first = client.post(
        f"/api/v3/households/{household_id}/plans/approve",
        json={
            "actor": "test-user",
            "reason": "first approval",
            "option": first_option,
        },
    ).json()
    second = client.post(
        f"/api/v3/households/{household_id}/plans/approve",
        json={
            "actor": "test-user",
            "reason": "second approval",
            "option": second_option,
        },
    ).json()

    accepted = client.get(f"/api/v3/households/{household_id}/plans/accepted/latest")

    assert accepted.status_code == 200
    accepted_plan = accepted.json()
    assert accepted_plan["id"] == second["approved_payload"]["accepted_plan_id"]
    assert accepted_plan["id"] != first["approved_payload"]["accepted_plan_id"]
    assert accepted_plan["status"] == "active"


def test_shopping_item_decision_creates_append_only_event() -> None:
    household_id = client.get("/api/v3/households/demo").json()["id"]
    option = _draft_plan_option()
    approval = client.post(
        f"/api/v3/households/{household_id}/plans/approve",
        json={
            "actor": "test-user",
            "reason": "approved before shopping review",
            "option": option,
        },
    ).json()
    accepted_plan_id = approval["approved_payload"]["accepted_plan_id"]
    item = approval["approved_payload"]["shopping_list"][0]

    response = client.post(
        f"/api/v3/households/{household_id}/shopping-list/decide",
        json={
            "accepted_plan_id": accepted_plan_id,
            "item_index": 0,
            "item_payload": item,
            "decision": "approved",
            "actor": "test-user",
            "reason": "needed for approved plan",
        },
    )

    assert response.status_code == 200
    event = response.json()
    assert event["event_type"] == "shopping_item_approved"
    assert event["target_type"] == "shopping_item"
    assert event["status"] == "approved"
    assert event["approved_payload"]["accepted_plan_id"] == accepted_plan_id
    assert event["approved_payload"]["item_index"] == 0

    changed_without_payload = client.post(
        f"/api/v3/households/{household_id}/shopping-list/decide",
        json={
            "accepted_plan_id": accepted_plan_id,
            "item_index": 0,
            "item_payload": item,
            "decision": "changed",
            "actor": "test-user",
            "reason": "replace this item",
        },
    )
    assert changed_without_payload.status_code == 422

    audit = client.get(f"/api/v3/households/{household_id}/audit-events").json()
    assert any(
        item["event_type"] == "shopping_item_approved" and item["object_id"] == event["id"] for item in audit
    )


def test_purchase_event_records_confirmed_pantry_lots_and_audit_event() -> None:
    household_id = client.get("/api/v3/households/demo").json()["id"]
    option = _draft_plan_option()
    approval = client.post(
        f"/api/v3/households/{household_id}/plans/approve",
        json={
            "actor": "test-user",
            "reason": "approved before purchase",
            "option": option,
        },
    ).json()
    accepted_plan_id = approval["approved_payload"]["accepted_plan_id"]
    item = approval["approved_payload"]["shopping_list"][0]
    shopping_decision = client.post(
        f"/api/v3/households/{household_id}/shopping-list/decide",
        json={
            "accepted_plan_id": accepted_plan_id,
            "item_index": 0,
            "item_payload": item,
            "decision": "approved",
            "actor": "test-user",
            "reason": "buy this for the approved plan",
        },
    ).json()

    purchase = client.post(
        f"/api/v3/households/{household_id}/purchases",
        json={
            "source": "shopping_list",
            "accepted_plan_id": accepted_plan_id,
            "shopping_decision_event_id": shopping_decision["id"],
            "items": [{"name": "milk", "quantity": 2, "unit": "pcs", "confidence": 1}],
            "total_cost": 180,
            "currency": "rub",
            "actor": "test-user",
            "reason": "confirmed after shopping",
        },
    )

    assert purchase.status_code == 200
    data = purchase.json()
    event = data["event"]
    lot = data["pantry_lots"][0]
    assert event["source"] == "shopping_list"
    assert event["accepted_plan_id"] == accepted_plan_id
    assert event["shopping_decision_event_id"] == shopping_decision["id"]
    assert event["currency"] == "RUB"
    assert event["pantry_lot_ids"] == [lot["id"]]
    assert lot["display_name"] == "milk"
    assert lot["source"] == "purchase:shopping_list"
    assert "explicit user action" in data["assistant_boundary"]

    purchases = client.get(f"/api/v3/households/{household_id}/purchases").json()
    assert any(item["id"] == event["id"] for item in purchases)

    pantry = client.get(f"/api/v3/households/{household_id}/pantry").json()
    assert any(item["id"] == lot["id"] for item in pantry)

    audit = client.get(f"/api/v3/households/{household_id}/audit-events").json()
    assert any(
        item["event_type"] == "purchase_recorded" and item["object_id"] == event["id"] for item in audit
    )


def test_purchase_event_rejects_missing_accepted_plan() -> None:
    household_id = client.get("/api/v3/households/demo").json()["id"]

    response = client.post(
        f"/api/v3/households/{household_id}/purchases",
        json={
            "source": "shopping_list",
            "accepted_plan_id": "missing-plan",
            "items": [{"name": "eggs", "quantity": 1}],
            "reason": "should fail because linked plan is missing",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Accepted plan not found"


def test_consumption_event_records_self_reported_meal_and_updates_summary_report() -> None:
    household_id = client.get("/api/v3/households/demo").json()["id"]
    option = _draft_plan_option()
    approval = client.post(
        f"/api/v3/households/{household_id}/plans/approve",
        json={
            "actor": "test-user",
            "reason": "approved before meal logging",
            "option": option,
        },
    ).json()
    accepted_plan_id = approval["approved_payload"]["accepted_plan_id"]

    response = client.post(
        f"/api/v3/households/{household_id}/consumption-events",
        json={
            "accepted_plan_id": accepted_plan_id,
            "day": 1,
            "meal": "breakfast",
            "status": "consumed",
            "servings": 1,
            "actor": "test-user",
            "reason": "ate the planned breakfast",
        },
    )

    assert response.status_code == 200
    data = response.json()
    event = data["event"]
    assert event["accepted_plan_id"] == accepted_plan_id
    assert event["status"] == "consumed"
    assert event["meal"] == "breakfast"
    assert event["recipe_title"]
    assert event["nutrition_payload"]["protein_g"] > 0
    assert "self-reported user facts" in data["assistant_boundary"]

    events = client.get(
        f"/api/v3/households/{household_id}/consumption-events",
        params={"accepted_plan_id": accepted_plan_id},
    ).json()
    assert any(item["id"] == event["id"] for item in events)

    report = client.get(
        f"/api/v3/households/{household_id}/reports/summary",
        params={"period_days": 3, "protein_goal_g": 95, "budget_per_day": 520},
    ).json()
    metrics = {item["key"]: item for item in report["metrics"]}
    assert event["id"] in report["generated_from"]["consumption_event_ids"]
    assert metrics["actual_protein"]["value"] >= event["nutrition_payload"]["protein_g"]
    assert metrics["actual_protein_goal_coverage"]["unit"] == "%"
    assert metrics["logged_meals"]["value"] >= 1

    audit = client.get(f"/api/v3/households/{household_id}/audit-events").json()
    assert any(item["event_type"] == "meal_consumed" and item["object_id"] == event["id"] for item in audit)


def test_changed_consumption_event_requires_override_payload() -> None:
    household_id = client.get("/api/v3/households/demo").json()["id"]
    option = _draft_plan_option()
    approval = client.post(
        f"/api/v3/households/{household_id}/plans/approve",
        json={"actor": "test-user", "reason": "approved before changed meal", "option": option},
    ).json()

    response = client.post(
        f"/api/v3/households/{household_id}/consumption-events",
        json={
            "accepted_plan_id": approval["approved_payload"]["accepted_plan_id"],
            "day": 1,
            "meal": "lunch",
            "status": "changed",
            "reason": "ate a different lunch",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "override_payload is required for changed consumption events"


def test_household_summary_report_uses_accepted_plan_and_purchase_history() -> None:
    household_id = client.get("/api/v3/households/demo").json()["id"]
    option = _draft_plan_option()
    approval = client.post(
        f"/api/v3/households/{household_id}/plans/approve",
        json={
            "actor": "test-user",
            "reason": "approved before reporting",
            "option": option,
        },
    ).json()
    accepted_plan_id = approval["approved_payload"]["accepted_plan_id"]
    purchase = client.post(
        f"/api/v3/households/{household_id}/purchases",
        json={
            "source": "manual",
            "accepted_plan_id": accepted_plan_id,
            "items": [{"name": "yogurt", "quantity": 3, "unit": "pcs"}],
            "total_cost": 240,
            "currency": "RUB",
            "reason": "confirmed before report",
        },
    ).json()

    report = client.get(
        f"/api/v3/households/{household_id}/reports/summary",
        params={"period_days": 3, "protein_goal_g": 95, "budget_per_day": 520},
    )

    assert report.status_code == 200
    data = report.json()
    metrics = {item["key"]: item for item in data["metrics"]}
    assert data["has_accepted_plan"] is True
    assert data["accepted_plan_id"] == accepted_plan_id
    assert data["generated_from"]["accepted_plan_id"] == accepted_plan_id
    assert purchase["event"]["id"] in data["generated_from"]["purchase_event_ids"]
    assert metrics["planned_protein"]["value"] > 0
    assert metrics["protein_goal_coverage"]["unit"] == "%"
    assert metrics["purchase_events"]["value"] >= 1
    assert metrics["purchased_items"]["value"] >= 1
    assert metrics["purchase_total_cost"]["value"] >= 240
    assert "self-reported consumption events" in data["assistant_boundary"]


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
    observations = client.get("/api/v3/households/unknown-household/observations")
    create_observation = client.post(
        "/api/v3/households/unknown-household/observations",
        json={
            "source": "manual",
            "candidates": [
                {
                    "name": "eggs",
                    "quantity": 1,
                    "reason": "manual candidate",
                }
            ],
        },
    )
    confirm_observation = client.post(
        "/api/v3/households/unknown-household/observations/missing/confirm",
        json={
            "candidates": [
                {
                    "candidate_id": "missing",
                    "item": {"name": "eggs", "quantity": 1},
                }
            ]
        },
    )

    assert pantry.status_code == 404
    assert confirm.status_code == 404
    assert observations.status_code == 404
    assert create_observation.status_code == 404
    assert confirm_observation.status_code == 404


def test_unknown_household_returns_404_for_plan_decisions() -> None:
    option = _draft_plan_option()
    approval_events = client.get("/api/v3/households/unknown-household/approval-events")
    latest_plan = client.get("/api/v3/households/unknown-household/plans/accepted/latest")
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
    shopping_decision = client.post(
        "/api/v3/households/unknown-household/shopping-list/decide",
        json={
            "accepted_plan_id": "missing",
            "item_index": 0,
            "item_payload": {"name": "eggs"},
            "decision": "approved",
            "reason": "needed",
        },
    )
    consent_history = client.get("/api/v3/households/unknown-household/consent-events")
    current_consents = client.get("/api/v3/households/unknown-household/consents/current")
    consent_create = client.post(
        "/api/v3/households/unknown-household/consent-events",
        json={
            "consent_type": "analytics",
            "status": "granted",
            "reason": "test consent",
        },
    )
    purchases = client.get("/api/v3/households/unknown-household/purchases")
    purchase_create = client.post(
        "/api/v3/households/unknown-household/purchases",
        json={
            "items": [{"name": "eggs", "quantity": 1}],
            "reason": "test purchase",
        },
    )
    consumption_history = client.get("/api/v3/households/unknown-household/consumption-events")
    consumption_create = client.post(
        "/api/v3/households/unknown-household/consumption-events",
        json={
            "accepted_plan_id": "missing-plan",
            "day": 1,
            "meal": "breakfast",
            "reason": "test consumption",
        },
    )
    report = client.get("/api/v3/households/unknown-household/reports/summary")

    assert approval_events.status_code == 404
    assert latest_plan.status_code == 404
    assert approve.status_code == 404
    assert override.status_code == 404
    assert shopping_decision.status_code == 404
    assert consent_history.status_code == 404
    assert current_consents.status_code == 404
    assert consent_create.status_code == 404
    assert purchases.status_code == 404
    assert purchase_create.status_code == 404
    assert consumption_history.status_code == 404
    assert consumption_create.status_code == 404
    assert report.status_code == 404
