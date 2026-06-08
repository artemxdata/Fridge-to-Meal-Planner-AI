from __future__ import annotations

import re

from app.catalog import PRODUCT_CATEGORIES, normalize_name
from app.schemas import DetectedIngredient, PerceptionParseRequest, PerceptionParseResponse

BARCODE_CATALOG: dict[str, tuple[str, float]] = {
    "4600000000011": ("молоко", 0.92),
    "4600000000028": ("йогурт", 0.92),
    "4600000000035": ("творог", 0.92),
    "4600000000042": ("яйца", 0.92),
    "4600000000059": ("курица", 0.90),
    "4600000000066": ("гречка", 0.90),
    "4600000000073": ("рис", 0.90),
    "4600000000080": ("паста", 0.90),
}

EXTRA_PRODUCTS = {
    "банан",
    "гранола",
    "изюм",
    "кефир",
    "колбаса",
    "маслины",
    "свинина",
    "сливки",
    "фасоль",
    "фарш",
    "хлеб",
    "чеснок",
}
KNOWN_PRODUCTS = sorted(set(PRODUCT_CATEGORIES) | EXTRA_PRODUCTS, key=len, reverse=True)
QUANTITY_RE = re.compile(r"(?P<value>\d+(?:[,.]\d+)?)\s*(?P<unit>кг|kg|г|g|л|l|шт|pcs|уп|x)?", re.I)


def parse_quantity(text: str) -> tuple[float, str]:
    matches = list(QUANTITY_RE.finditer(text))
    if not matches:
        return 1.0, "шт"
    match = matches[-1]
    value = float(match.group("value").replace(",", "."))
    unit = (match.group("unit") or "шт").lower()
    unit_map = {
        "kg": "кг",
        "g": "г",
        "l": "л",
        "pcs": "шт",
        "x": "шт",
        "уп": "шт",
    }
    return value, unit_map.get(unit, unit)


def merge_candidates(items: list[DetectedIngredient]) -> list[DetectedIngredient]:
    merged: dict[str, DetectedIngredient] = {}
    for item in items:
        key = normalize_name(item.name)
        if not key:
            continue
        existing = merged.get(key)
        if existing is None:
            merged[key] = item
            continue
        if existing.unit == item.unit:
            existing.quantity = round(existing.quantity + item.quantity, 2)
        existing.confidence = max(existing.confidence, item.confidence)
        existing.reason = f"{existing.reason}; {item.reason}"
    return sorted(merged.values(), key=lambda item: (-item.confidence, item.name))


def parse_text_candidates(raw_text: str, source: str) -> list[DetectedIngredient]:
    candidates = []
    for line in raw_text.splitlines():
        normalized_line = normalize_name(line)
        if not normalized_line:
            continue
        for product in KNOWN_PRODUCTS:
            if product not in normalized_line:
                continue
            quantity, unit = parse_quantity(normalized_line.replace(product, " "))
            candidates.append(
                DetectedIngredient(
                    name=product,
                    quantity=quantity,
                    unit=unit,
                    confidence=0.78,
                    source=f"{source}_text",
                    reason="matched product name in receipt/OCR text",
                )
            )
            break
    return candidates


def parse_barcode_candidates(barcodes: list[str]) -> tuple[list[DetectedIngredient], list[str]]:
    items = []
    unknown = []
    for barcode in barcodes:
        normalized = re.sub(r"\D", "", barcode)
        product = BARCODE_CATALOG.get(normalized)
        if product is None:
            unknown.append(barcode)
            continue
        name, confidence = product
        items.append(
            DetectedIngredient(
                name=name,
                quantity=1,
                unit="шт",
                confidence=confidence,
                source="barcode_demo_catalog",
                reason=f"matched demo barcode {normalized}",
            )
        )
    return items, unknown


def parse_perception(request: PerceptionParseRequest) -> PerceptionParseResponse:
    text_items = parse_text_candidates(request.raw_text, request.source)
    barcode_items, unknown_barcodes = parse_barcode_candidates(request.barcodes)
    items = merge_candidates(text_items + barcode_items)
    notes = [
        "Receipt/barcode parsing is deterministic fallback, not autonomous pantry update.",
        "User must confirm or edit candidates before saving them to pantry.",
    ]
    if unknown_barcodes:
        notes.append("Unknown barcodes require manual review: " + ", ".join(unknown_barcodes[:5]))
    if not items:
        notes.append("No known products matched; enter items manually or improve OCR text.")
    fallback = "receipt_barcode_heuristics" if items else "manual_review_required"
    return PerceptionParseResponse(
        items=items,
        raw_text=request.raw_text,
        barcodes=request.barcodes,
        fallback=fallback,
        notes=notes,
    )
