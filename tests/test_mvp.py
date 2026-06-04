from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from run_ultra_smart_app import app


client = TestClient(app)


def test_root_and_frontend() -> None:
    root = client.get("/")
    frontend = client.get("/app")

    assert root.status_code == 200
    assert root.json()["ok"] is True
    assert root.json()["recipes"] > 0
    assert frontend.status_code == 200
    assert "Fridge-to-Meal Planner AI" in frontend.text


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
