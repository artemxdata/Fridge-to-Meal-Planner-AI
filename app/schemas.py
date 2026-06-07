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
