from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class PantryItem(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    quantity: float = Field(default=1, ge=0, le=100000)
    unit: str = Field(default="шт", min_length=1, max_length=30)
    expires_in_days: int | None = Field(default=None, ge=0, le=3650)
    source: str = Field(default="manual", max_length=50)
    confidence: float | None = Field(default=None, ge=0, le=1)

    @field_validator("name", "unit", "source")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class Nutrition(BaseModel):
    calories: int = Field(ge=0)
    protein: float = Field(ge=0)
    carbs: float = Field(ge=0)
    fats: float = Field(ge=0)


class Recipe(BaseModel):
    id: int
    title: str
    meal: str
    season_tags: list[str] = Field(default_factory=list)
    ingredients: dict[str, float]
    cost_per_serving: float = Field(ge=0)
    servings: int = Field(default=1, ge=1)
    time_min: int = Field(default=15, ge=1)
    difficulty: str = "easy"
    nutrition: Nutrition


class SuggestRequest(BaseModel):
    pantry: list[PantryItem] = Field(default_factory=list, max_length=300)
    budget: float = Field(default=500, gt=0)
    season: str | None = None
    meal: str | None = None


class PlanRequest(BaseModel):
    pantry: list[PantryItem] = Field(default_factory=list, max_length=300)
    budget_per_day: float = Field(default=500, gt=0)
    season: str | None = None
    target_calories: int | None = Field(default=1800, ge=0, le=10000)
    meal_preference: str | None = "day"
    protein_goal_g: int | None = Field(default=100, ge=0, le=1000)
    carbs_goal_g: int | None = Field(default=180, ge=0, le=2000)
    fats_goal_g: int | None = Field(default=60, ge=0, le=1000)


class ThreeDayPlanRequest(PlanRequest):
    days: int = Field(default=3, ge=1, le=3)


class PlanResponse(BaseModel):
    meals: dict[str, Recipe]
    totals: dict[str, Any]
    shopping_gaps: list[str]
    notes: list[str]


class DetectedIngredient(BaseModel):
    name: str
    quantity: float = Field(default=1, ge=0)
    unit: str = "шт"
    expires_in_days: int | None = Field(default=None, ge=0)
    confidence: float = Field(default=0.5, ge=0, le=1)
    source: str = "fallback"
    reason: str


class VisionResponse(BaseModel):
    items: list[DetectedIngredient]
    raw_text: str = ""
    image_quality: dict[str, Any]
    needs_confirmation: bool = True
    fallback: str
    notes: list[str]


class PerceptionParseRequest(BaseModel):
    raw_text: str = Field(default="", max_length=5000)
    barcodes: list[str] = Field(default_factory=list, max_length=50)
    source: Literal["receipt", "barcode", "label", "manual_ocr"] = "receipt"

    @field_validator("barcodes")
    @classmethod
    def strip_barcodes(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]


class PerceptionParseResponse(BaseModel):
    items: list[DetectedIngredient]
    raw_text: str = ""
    barcodes: list[str] = Field(default_factory=list)
    needs_confirmation: bool = True
    fallback: str
    notes: list[str]


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str


PlanStrategy = Literal["simple", "waste_first", "balanced"]


class PolicyConstraints(BaseModel):
    allergies: list[str] = Field(default_factory=list, max_length=50)
    disliked_ingredients: list[str] = Field(default_factory=list, max_length=100)
    max_cooking_time_min: int | None = Field(default=None, ge=1, le=240)
    no_shop_mode: bool = False
    low_dishes: bool = False
    strict_budget: bool = False

    @field_validator("allergies", "disliked_ingredients")
    @classmethod
    def strip_list_values(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]


class PlanOptionsRequest(ThreeDayPlanRequest):
    context_note: str | None = Field(default=None, max_length=1000)
    policy: PolicyConstraints = Field(default_factory=PolicyConstraints)


class DecisionTraceItem(BaseModel):
    rule: str
    reason: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class PlanOption(BaseModel):
    option_id: str
    strategy: PlanStrategy
    title: str
    summary: str
    plan: dict[str, Any]
    decision_trace: list[DecisionTraceItem]
    approval_status: Literal["draft"] = "draft"
    requires_approval: bool = True


class PlanOptionsResponse(BaseModel):
    options: list[PlanOption]
    assistant_boundary: str


class ContextInterpretRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class ContextInterpretResponse(BaseModel):
    proposed_constraints: dict[str, Any]
    evidence: list[str]
    requires_confirmation: bool = True


CompanionMood = Literal[
    "steady",
    "needs_protein",
    "budget_watch",
    "use_soon",
    "shopping_heavy",
    "overloaded",
]


class CompanionSignal(BaseModel):
    key: str
    label: str
    value: str
    status: Literal["good", "watch", "action"]
    explanation: str
    source: str


class CompanionStateRequest(BaseModel):
    plan: dict[str, Any] = Field(default_factory=dict)
    pantry: list[PantryItem] = Field(default_factory=list, max_length=300)
    protein_goal_g: int | None = Field(default=100, ge=0, le=1000)
    budget_per_day: float = Field(default=500, gt=0)
    days: int = Field(default=3, ge=1, le=14)
    mascot: Literal["nerpa", "sunflower", "kitchen_helper"] = "nerpa"


class CompanionStateResponse(BaseModel):
    mascot: str
    state: CompanionMood
    display_name: str
    score: int = Field(ge=0, le=100)
    message: str
    visual_hint: str
    signals: list[CompanionSignal]
    assistant_boundary: str


class HouseholdResponse(BaseModel):
    id: str
    name: str
    locale: str
    created_at: str


class PantryLotResponse(BaseModel):
    id: str
    household_id: str
    ingredient_name: str
    display_name: str
    quantity: float
    unit: str
    expires_in_days: int | None
    source: str
    confidence: float | None
    status: str
    created_at: str
    updated_at: str


ObservationSource = Literal["photo", "receipt", "barcode", "label", "manual_ocr", "manual"]


class ObservationSessionCreateRequest(BaseModel):
    source: ObservationSource
    candidates: list[DetectedIngredient] = Field(min_length=1, max_length=100)
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    actor: str = Field(default="demo-user", min_length=1, max_length=80)
    reason: str = Field(default="stored_observation_candidates", min_length=1, max_length=500)


class ObservationCandidateResponse(BaseModel):
    id: str
    session_id: str
    household_id: str
    ingredient_name: str
    display_name: str
    quantity: float
    unit: str
    expires_in_days: int | None
    source: str
    confidence: float
    reason: str
    status: str
    created_at: str
    updated_at: str
    confirmed_at: str | None


class ObservationSessionResponse(BaseModel):
    id: str
    household_id: str
    source: str
    status: str
    needs_confirmation: bool
    raw_payload: dict[str, Any]
    candidates: list[ObservationCandidateResponse]
    created_at: str
    updated_at: str


class ObservationCandidateConfirmation(BaseModel):
    candidate_id: str = Field(min_length=1, max_length=120)
    item: PantryItem


class ObservationConfirmRequest(BaseModel):
    candidates: list[ObservationCandidateConfirmation] = Field(min_length=1, max_length=100)
    actor: str = Field(default="demo-user", min_length=1, max_length=80)
    reason: str = Field(default="user_confirmed_observation_candidates", min_length=1, max_length=500)


class PantryConfirmationRequest(BaseModel):
    items: list[PantryItem] = Field(default_factory=list, min_length=1, max_length=100)
    actor: str = Field(default="demo-user", min_length=1, max_length=80)
    reason: str = Field(default="user_confirmed_pantry_candidates", max_length=500)


class AuditEventResponse(BaseModel):
    id: str
    household_id: str
    event_type: str
    actor: str
    object_type: str
    object_id: str | None
    reason: str
    payload: dict[str, Any]
    created_at: str


ConsentType = Literal[
    "photo_retention",
    "receipt_retention",
    "analytics",
    "model_training",
    "product_research",
]
ConsentStatus = Literal["granted", "revoked", "denied"]


class ConsentEventCreateRequest(BaseModel):
    consent_type: ConsentType
    status: ConsentStatus
    scope: str = Field(default="household", min_length=1, max_length=120)
    actor: str = Field(default="demo-user", min_length=1, max_length=80)
    reason: str = Field(min_length=3, max_length=500)
    policy_version: str = Field(default="privacy-v1", min_length=1, max_length=80)
    source: str = Field(default="user_action", min_length=1, max_length=80)
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("scope", "actor", "reason", "policy_version", "source")
    @classmethod
    def strip_text_values(cls, value: str) -> str:
        return value.strip()


class ConsentEventResponse(BaseModel):
    id: str
    household_id: str
    consent_type: str
    scope: str
    status: str
    actor: str
    reason: str
    policy_version: str
    source: str
    payload: dict[str, Any]
    created_at: str


class CurrentConsentResponse(BaseModel):
    consents: list[ConsentEventResponse]
    assistant_boundary: str


PurchaseSource = Literal["manual", "shopping_list", "receipt_import", "correction"]


class PurchaseEventCreateRequest(BaseModel):
    items: list[PantryItem] = Field(min_length=1, max_length=100)
    source: PurchaseSource = "manual"
    accepted_plan_id: str | None = Field(default=None, min_length=1, max_length=120)
    shopping_decision_event_id: str | None = Field(default=None, min_length=1, max_length=120)
    total_cost: float | None = Field(default=None, ge=0, le=10000000)
    currency: str = Field(default="RUB", min_length=1, max_length=10)
    actor: str = Field(default="demo-user", min_length=1, max_length=80)
    reason: str = Field(default="user_recorded_purchase", min_length=1, max_length=500)

    @field_validator("accepted_plan_id", "shopping_decision_event_id")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("actor", "reason")
    @classmethod
    def strip_purchase_text(cls, value: str) -> str:
        return value.strip()


class PurchaseEventResponse(BaseModel):
    id: str
    household_id: str
    source: str
    accepted_plan_id: str | None
    shopping_decision_event_id: str | None
    actor: str
    reason: str
    total_cost: float | None
    currency: str
    items_payload: list[dict[str, Any]]
    pantry_lot_ids: list[str]
    created_at: str


class PurchaseRecordResponse(BaseModel):
    event: PurchaseEventResponse
    pantry_lots: list[PantryLotResponse]
    assistant_boundary: str


ConsumptionStatus = Literal["consumed", "skipped", "changed"]


class ConsumptionEventCreateRequest(BaseModel):
    accepted_plan_id: str = Field(min_length=1, max_length=120)
    day: int = Field(ge=1, le=14)
    meal: str = Field(min_length=1, max_length=40)
    status: ConsumptionStatus = "consumed"
    servings: float = Field(default=1, ge=0, le=20)
    actor: str = Field(default="demo-user", min_length=1, max_length=80)
    reason: str = Field(default="user_confirmed_meal_consumption", min_length=1, max_length=500)
    nutrition_payload: dict[str, Any] = Field(default_factory=dict)
    override_payload: dict[str, Any] = Field(default_factory=dict)
    consumed_at: str | None = Field(default=None, max_length=40)

    @field_validator("accepted_plan_id", "meal", "actor", "reason")
    @classmethod
    def strip_consumption_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("consumed_at")
    @classmethod
    def strip_consumed_at(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class ConsumptionEventResponse(BaseModel):
    id: str
    household_id: str
    accepted_plan_id: str
    day: int
    meal: str
    status: str
    servings: float
    actor: str
    reason: str
    recipe_title: str | None
    nutrition_payload: dict[str, Any]
    override_payload: dict[str, Any]
    consumed_at: str | None
    created_at: str


class ConsumptionRecordResponse(BaseModel):
    event: ConsumptionEventResponse
    assistant_boundary: str


class ReportMetric(BaseModel):
    key: str
    label: str
    value: float | int | str | None
    unit: str | None = None
    status: Literal["good", "watch", "action", "neutral"] = "neutral"
    source: str
    explanation: str


class HouseholdSummaryReportResponse(BaseModel):
    household_id: str
    period_days: int
    has_accepted_plan: bool
    accepted_plan_id: str | None
    generated_from: dict[str, Any]
    metrics: list[ReportMetric]
    insights: list[str]
    assistant_boundary: str


class PlanApprovalRequest(BaseModel):
    option: PlanOption
    actor: str = Field(default="demo-user", min_length=1, max_length=80)
    reason: str = Field(default="user_approved_plan_draft", min_length=1, max_length=500)


class PlanOverrideRequest(BaseModel):
    original_option: PlanOption
    override_payload: dict[str, Any] = Field(default_factory=dict)
    actor: str = Field(default="demo-user", min_length=1, max_length=80)
    reason: str = Field(min_length=3, max_length=500)


class ApprovalEventResponse(BaseModel):
    id: str
    household_id: str
    event_type: str
    actor: str
    target_type: str
    target_id: str
    status: str
    reason: str
    proposal_payload: dict[str, Any]
    approved_payload: dict[str, Any]
    override_payload: dict[str, Any]
    created_at: str


class AcceptedPlanResponse(BaseModel):
    id: str
    household_id: str
    source_approval_event_id: str
    option_id: str
    strategy: str
    title: str
    status: str
    plan_payload: dict[str, Any]
    shopping_list_payload: list[dict[str, Any]]
    created_at: str
    updated_at: str


ShoppingDecisionStatus = Literal["approved", "skipped", "changed"]


class ShoppingItemDecisionRequest(BaseModel):
    accepted_plan_id: str = Field(min_length=1, max_length=120)
    item_index: int = Field(ge=0, le=500)
    item_payload: dict[str, Any] = Field(default_factory=dict)
    decision: ShoppingDecisionStatus
    actor: str = Field(default="demo-user", min_length=1, max_length=80)
    reason: str = Field(min_length=3, max_length=500)
    override_payload: dict[str, Any] = Field(default_factory=dict)
