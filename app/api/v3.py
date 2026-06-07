from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas import (
    ApprovalEventResponse,
    AuditEventResponse,
    ContextInterpretRequest,
    ContextInterpretResponse,
    HouseholdResponse,
    PantryConfirmationRequest,
    PantryLotResponse,
    PlanApprovalRequest,
    PlanOptionsRequest,
    PlanOptionsResponse,
    PlanOverrideRequest,
)
from app.services.approvals import (
    approval_event_response,
    approve_plan_option,
    list_approval_events,
    override_plan_option,
)
from app.services.context import interpret_context
from app.services.households import (
    audit_event_response,
    confirm_pantry_items,
    get_household,
    get_or_create_demo_household,
    household_response,
    list_audit_events,
    list_pantry_lots,
    pantry_lot_response,
)
from app.services.planner import build_plan_options

router = APIRouter(prefix="/api/v3", tags=["Human-controlled planning v3"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post("/assistant/interpret-context", response_model=ContextInterpretResponse)
def interpret_user_context(request: ContextInterpretRequest) -> ContextInterpretResponse:
    return interpret_context(request.text)


@router.post("/plans/options", response_model=PlanOptionsResponse)
def plan_options(request: PlanOptionsRequest) -> PlanOptionsResponse:
    return build_plan_options(request)


@router.get("/households/{household_id}/approval-events", response_model=list[ApprovalEventResponse])
async def approval_events(
    household_id: str, session: SessionDep, limit: int = 50
) -> list[ApprovalEventResponse]:
    household = await get_household(session, household_id)
    if household is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Household not found")
    events = await list_approval_events(session, household_id, max(1, min(limit, 100)))
    return [approval_event_response(event) for event in events]


@router.post("/households/{household_id}/plans/approve", response_model=ApprovalEventResponse)
async def approve_plan(
    household_id: str,
    request: PlanApprovalRequest,
    session: SessionDep,
) -> ApprovalEventResponse:
    household = await get_household(session, household_id)
    if household is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Household not found")
    event = await approve_plan_option(session, household_id=household_id, request=request)
    return approval_event_response(event)


@router.post("/households/{household_id}/plans/override", response_model=ApprovalEventResponse)
async def override_plan(
    household_id: str,
    request: PlanOverrideRequest,
    session: SessionDep,
) -> ApprovalEventResponse:
    household = await get_household(session, household_id)
    if household is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Household not found")
    if not request.override_payload:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "override_payload is required")
    event = await override_plan_option(session, household_id=household_id, request=request)
    return approval_event_response(event)


@router.get("/households/demo", response_model=HouseholdResponse)
async def demo_household(session: SessionDep) -> HouseholdResponse:
    household = await get_or_create_demo_household(session)
    return household_response(household)


@router.get("/households/{household_id}/pantry", response_model=list[PantryLotResponse])
async def pantry_lots(household_id: str, session: SessionDep) -> list[PantryLotResponse]:
    household = await get_household(session, household_id)
    if household is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Household not found")
    lots = await list_pantry_lots(session, household_id)
    return [pantry_lot_response(lot) for lot in lots]


@router.post("/households/{household_id}/pantry/confirm", response_model=list[PantryLotResponse])
async def confirm_pantry(
    household_id: str,
    request: PantryConfirmationRequest,
    session: SessionDep,
) -> list[PantryLotResponse]:
    household = await get_household(session, household_id)
    if household is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Household not found")
    lots = await confirm_pantry_items(
        session,
        household_id=household_id,
        items=request.items,
        actor=request.actor,
        reason=request.reason,
    )
    return [pantry_lot_response(lot) for lot in lots]


@router.get("/households/{household_id}/audit-events", response_model=list[AuditEventResponse])
async def audit_events(household_id: str, session: SessionDep, limit: int = 50) -> list[AuditEventResponse]:
    household = await get_household(session, household_id)
    if household is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Household not found")
    events = await list_audit_events(session, household_id, max(1, min(limit, 100)))
    return [audit_event_response(event) for event in events]
