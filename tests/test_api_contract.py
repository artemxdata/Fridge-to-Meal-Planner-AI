from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app

client = TestClient(app)


def image_file(color: tuple[int, int, int] = (210, 40, 35)) -> BytesIO:
    image = Image.new("RGB", (120, 120), color)
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    buffer.seek(0)
    return buffer


def test_health_and_request_trace() -> None:
    live = client.get("/health/live", headers={"X-Request-ID": "test-request"})
    ready = client.get("/health/ready")

    assert live.status_code == 200
    assert live.headers["X-Request-ID"] == "test-request"
    assert live.json()["status"] == "ok"
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"


def test_v2_contract_remains_available() -> None:
    demo = client.get("/api/v2/demo")
    sample = client.get("/api/v2/recipes/sample?n=2")

    assert demo.status_code == 200
    assert demo.json()["pantry"]
    assert sample.status_code == 200
    assert len(sample.json()) == 2


def test_photo_endpoint_rejects_non_image_and_invalid_mode() -> None:
    non_image = client.post(
        "/api/v2/vision/analyze",
        files={"file": ("payload.txt", b"not an image", "text/plain")},
    )
    invalid_mode = client.post(
        "/api/v2/vision/analyze",
        files={"file": ("fridge.jpg", image_file(), "image/jpeg")},
        data={"mode": "autonomous"},
    )

    assert non_image.status_code == 415
    assert invalid_mode.status_code == 422


def test_invalid_pantry_quantity_is_rejected() -> None:
    response = client.post(
        "/api/v2/plan",
        json={
            "pantry": [{"name": "яйца", "quantity": -1}],
            "budget_per_day": 500,
        },
    )

    assert response.status_code == 422


def test_vision_candidates_always_require_confirmation() -> None:
    response = client.post(
        "/api/v2/vision/analyze",
        files={"file": ("tomato.jpg", image_file(), "image/jpeg")},
        data={"text_hint": "помидоры"},
    )

    assert response.status_code == 200
    assert response.json()["needs_confirmation"] is True


def test_receipt_and_barcode_parser_returns_confirmable_candidates() -> None:
    response = client.post(
        "/api/v2/perception/parse",
        json={
            "source": "receipt",
            "raw_text": "Йогурт 2 шт\nКартофель 3 кг\nЯйца 10 шт",
            "barcodes": ["4600000000011", "unknown-code"],
        },
    )

    assert response.status_code == 200
    data = response.json()
    names = {item["name"] for item in data["items"]}
    assert {"йогурт", "картофель", "яйца", "молоко"} <= names
    assert data["needs_confirmation"] is True
    assert data["fallback"] == "receipt_barcode_heuristics"
    assert any("Unknown barcodes" in note for note in data["notes"])
