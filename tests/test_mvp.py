from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from app.config import settings
from run_ultra_smart_app import app

client = TestClient(app)


def test_root_and_frontend() -> None:
    root = client.get("/")
    frontend = client.get("/app")

    assert root.status_code == 200
    assert root.json()["ok"] is True
    assert root.json()["recipes"] > 0
    assert root.json()["pwa"] == "/pwa"
    assert frontend.status_code == 200
    assert "Fridge-to-Meal Planner AI" in frontend.text
    assert "/api/v3/plans/options" in frontend.text
    assert "/api/v3/households/${householdId}/plans/approve" in frontend.text
    assert "/api/v3/households/${householdId}/shopping-list/decide" in frontend.text
    assert "/api/v2/perception/parse" in frontend.text
    assert "/api/v3/companion/state" in frontend.text
    assert "/api/v3/households/${householdId}/observations" in frontend.text
    assert "/api/v3/households/${householdId}/observations/${observationSessionId}/confirm" in frontend.text
    assert "Companion" in frontend.text
    assert "no_shop_mode" in frontend.text


def test_react_pwa_route_serves_build_when_available() -> None:
    response = client.get("/pwa")

    if not settings.react_frontend_path.exists():
        assert response.status_code == 404
        assert "React build not found" in response.text
        return

    assert response.status_code == 200
    assert '<div id="root"></div>' in response.text


def test_react_pwa_root_assets_are_served_when_build_exists() -> None:
    for route in ["/manifest.webmanifest", "/service-worker.js", "/pwa-icon.svg"]:
        response = client.get(route)

        if not settings.react_frontend_path.exists():
            assert response.status_code == 404
            assert "React PWA asset not found" in response.text
            continue

        assert response.status_code == 200


def test_demo_generates_three_day_plan_and_shopping_list() -> None:
    demo = client.get("/api/v2/demo").json()
    response = client.post(
        "/api/v2/meal-plan/3-days",
        json={
            "pantry": demo["pantry"],
            "budget_per_day": demo["preferences"]["budget_per_day"],
            "season": demo["preferences"]["season"],
            "target_calories": demo["preferences"]["target_calories"],
            "protein_goal_g": demo["preferences"]["protein_goal_g"],
            "meal_preference": "day",
            "days": 3,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["days"]) == 3
    assert data["shopping_list"]
    assert data["statistics"]["recipes_count"] == 9
    assert all(item["reason"] for item in data["shopping_list"])


def test_photo_analysis_requires_manual_confirmation() -> None:
    image = Image.new("RGB", (120, 120), (210, 40, 35))
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    buffer.seek(0)

    response = client.post(
        "/api/v2/vision/analyze",
        files={"file": ("tomato.jpg", buffer, "image/jpeg")},
        data={"mode": "auto", "text_hint": "помидоры яйца"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["needs_confirmation"] is True
    assert data["items"]
    assert any(item["name"] == "помидор" for item in data["items"])
