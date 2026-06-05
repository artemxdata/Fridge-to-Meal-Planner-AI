from __future__ import annotations

from io import BytesIO
from typing import Any

from PIL import Image, ImageStat, UnidentifiedImageError

from app.catalog import DEMO_PANTRY, PRODUCT_CATEGORIES, normalize_name
from app.config import settings
from app.schemas import DetectedIngredient, VisionResponse


class InvalidImageError(ValueError):
    pass


class ImageTooLargeError(ValueError):
    pass


def decode_image(content: bytes) -> Image.Image:
    if len(content) > settings.max_upload_bytes:
        limit_mb = settings.max_upload_bytes // 1024 // 1024
        raise ImageTooLargeError(f"Файл слишком большой. Лимит: {limit_mb} MB")
    if not content:
        raise InvalidImageError("Загружен пустой файл")
    try:
        image = Image.open(BytesIO(content))
        if image.width * image.height > settings.max_image_pixels:
            raise ImageTooLargeError("Изображение имеет слишком большое разрешение")
        return image.convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        if isinstance(exc, ImageTooLargeError):
            raise
        raise InvalidImageError("Не удалось прочитать изображение") from exc


def image_quality(image: Image.Image) -> dict[str, Any]:
    stat = ImageStat.Stat(image.convert("L"))
    brightness = round(stat.mean[0], 2)
    contrast = round(stat.stddev[0], 2)
    return {
        "width": image.width,
        "height": image.height,
        "brightness": brightness,
        "contrast": contrast,
        "overall": "good" if 45 <= brightness <= 220 and contrast >= 25 else "needs_review",
    }


def color_fallback_detection(image: Image.Image) -> list[DetectedIngredient]:
    resized = image.convert("RGB").resize((80, 80))
    pixel_reader = getattr(resized, "get_flattened_data", resized.getdata)
    pixels = list(pixel_reader())
    total = max(1, len(pixels))
    ratios = {
        "red": sum(1 for r, g, b in pixels if r > 140 and g < 120 and b < 120) / total,
        "green": sum(1 for r, g, b in pixels if g > 120 and r < 130) / total,
        "yellow": sum(1 for r, g, b in pixels if r > 150 and g > 130 and b < 100) / total,
        "white": sum(1 for r, g, b in pixels if r > 190 and g > 190 and b > 180) / total,
    }
    rules = [
        ("red", 0.05, "помидор", 0.58, "на фото заметны красные области"),
        ("green", 0.08, "огурец", 0.52, "на фото заметны зелёные области"),
        ("yellow", 0.06, "банан", 0.50, "на фото заметны жёлтые области"),
        ("white", 0.12, "йогурт", 0.45, "на фото много светлых упаковок или продуктов"),
    ]
    return [
        DetectedIngredient(name=name, confidence=confidence, source="color_fallback", reason=reason)
        for color, threshold, name, confidence, reason in rules
        if ratios[color] > threshold
    ]


def text_fallback_detection(text: str) -> list[DetectedIngredient]:
    normalized_text = normalize_name(text)
    known_products = set(PRODUCT_CATEGORIES) | {"яйца", "помидор", "огурец", "курица", "йогурт", "творог"}
    return [
        DetectedIngredient(
            name=product,
            confidence=0.82,
            source="text_hint",
            reason="найдено в текстовой подсказке или названии файла",
        )
        for product in sorted(known_products)
        if product in normalized_text
    ]


def analyze_image(image: Image.Image, *, filename: str, text_hint: str, mode: str) -> VisionResponse:
    quality = image_quality(image)
    notes = [
        "MVP использует простую эвристику по цветам и текстовую подсказку.",
        "Перед добавлением в холодильник продукты нужно подтвердить вручную.",
    ]

    if mode == "demo":
        return VisionResponse(
            items=[
                DetectedIngredient(
                    name=item.name,
                    quantity=item.quantity,
                    unit=item.unit,
                    expires_in_days=item.expires_in_days,
                    confidence=item.confidence or 0.8,
                    source="demo",
                    reason="демо-сценарий",
                )
                for item in DEMO_PANTRY[:5]
            ],
            raw_text=text_hint,
            image_quality=quality,
            fallback="demo",
            notes=notes,
        )

    candidates = text_fallback_detection(f"{filename} {text_hint}") + color_fallback_detection(image)
    by_name: dict[str, DetectedIngredient] = {}
    for item in candidates:
        key = normalize_name(item.name)
        if key not in by_name or by_name[key].confidence < item.confidence:
            by_name[key] = item

    items = list(by_name.values())
    fallback = "color_text_heuristics"
    if not items:
        items = [
            DetectedIngredient(
                name=item.name,
                quantity=item.quantity,
                unit=item.unit,
                expires_in_days=item.expires_in_days,
                confidence=0.6,
                source="fallback_demo",
                reason="CV не нашёл уверенных объектов, подставлен безопасный demo-набор",
            )
            for item in DEMO_PANTRY[:4]
        ]
        fallback = "demo_pantry"
        notes.append("Распознавание не уверено: используйте список только как черновик.")

    return VisionResponse(
        items=items,
        raw_text=text_hint,
        image_quality=quality,
        fallback=fallback,
        notes=notes,
    )
