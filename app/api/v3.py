from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import HouseholdDep, SessionDep
from app.schemas import (
    AcceptedPlanResponse,
    ApprovalEventResponse,
    AuditEventResponse,
    CompanionStateRequest,
    CompanionStateResponse,
    ConsentEventCreateRequest,
    ConsentEventResponse,
    ContextInterpretRequest,
    ContextInterpretResponse,
    CurrentConsentResponse,
    HouseholdResponse,
    ObservationConfirmRequest,
    ObservationSessionCreateRequest,
    ObservationSessionResponse,
    PantryConfirmationRequest,
    PantryLotResponse,
    PlanApprovalRequest,
    PlanOptionsRequest,
    PlanOptionsResponse,
    PlanOverrideRequest,
    PurchaseEventCreateRequest,
    PurchaseEventResponse,
    PurchaseRecordResponse,
    ShoppingItemDecisionRequest,
)
from app.services.approvals import (
    accepted_plan_response,
    approval_event_response,
    approve_plan_option,
    decide_shopping_item,
    get_latest_accepted_plan,
    list_approval_events,
    override_plan_option,
)
from app.services.companion import build_companion_state
from app.services.consents import (
    consent_event_response,
    create_consent_event,
    current_consent_response,
    get_current_consents,
    list_consent_events,
)
from app.services.context import interpret_context
from app.services.households import (
    audit_event_response,
    confirm_pantry_items,
    get_or_create_demo_household,
    household_response,
    list_audit_events,
    list_pantry_lots,
    pantry_lot_response,
)
from app.services.observations import (
    confirm_observation_candidates,
    create_observation_session,
    list_observation_sessions,
    observation_session_response,
)
from app.services.planner import RecipeNotFoundError, build_plan_options
from app.services.purchases import (
    list_purchase_events,
    purchase_event_response,
    purchase_record_response,
    record_purchase_event,
)

router = APIRouter(prefix="/api/v3", tags=["Human-controlled planning v3"])


@router.post("/assistant/interpret-context", response_model=ContextInterpretResponse)
def interpret_user_context(request: ContextInterpretRequest) -> ContextInterpretResponse:
    return interpret_context(request.text)


@router.post("/plans/options", response_model=PlanOptionsResponse)
def plan_options(request: PlanOptionsRequest) -> PlanOptionsResponse:
    try:
        return build_plan_options(request)
    except RecipeNotFoundError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc


@router.post("/companion/state", response_model=CompanionStateResponse)
def companion_state(request: CompanionStateRequest) -> CompanionStateResponse:
    return build_companion_state(request)


@router.post(
    "/households/{household_id}/observations",
    response_model=ObservationSessionResponse,
)
async def create_observation(
    household_id: str,
    request: ObservationSessionCreateRequest,
    session: SessionDep,
    _household: HouseholdDep,
) -> ObservationSessionResponse:
    observation = await create_observation_session(session, household_id=household_id, request=request)
    return observation_session_response(observation)


@router.get(
    "/households/{household_id}/observations",
    response_model=list[ObservationSessionResponse],
)
async def observations(
    household_id: str,
    session: SessionDep,
    _household: HouseholdDep,
    limit: int = 20,
) -> list[ObservationSessionResponse]:
    rows = await list_observation_sessions(session, household_id, max(1, min(limit, 100)))
    return [observation_session_response(row) for row in rows]


@router.post(
    "/households/{household_id}/observations/{observation_id}/confirm",
    response_model=ObservationSessionResponse,
)
async def confirm_observation(
    household_id: str,
    observation_id: str,
    request: ObservationConfirmRequest,
    session: SessionDep,
    _household: HouseholdDep,
) -> ObservationSessionResponse:
    try:
        observation, _lots = await confirm_observation_candidates(
            session,
            household_id=household_id,
            observation_id=observation_id,
            request=request,
        )
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return observation_session_response(observation)


@router.get("/households/{household_id}/approval-events", response_model=list[ApprovalEventResponse])
async def approval_events(
    household_id: str, session: SessionDep, _household: HouseholdDep, limit: int = 50
) -> list[ApprovalEventResponse]:
    events = await list_approval_events(session, household_id, max(1, min(limit, 100)))
    return [approval_event_response(event) for event in events]


@router.post("/households/{household_id}/consent-events", response_model=ConsentEventResponse)
async def record_consent_event(
    household_id: str,
    request: ConsentEventCreateRequest,
    session: SessionDep,
    _household: HouseholdDep,
) -> ConsentEventResponse:
    event = await create_consent_event(session, household_id=household_id, request=request)
    return consent_event_response(event)


@router.get("/households/{household_id}/consent-events", response_model=list[ConsentEventResponse])
async def consent_events(
    household_id: str,
    session: SessionDep,
    _household: HouseholdDep,
    limit: int = 50,
) -> list[ConsentEventResponse]:
    events = await list_consent_events(session, household_id, max(1, min(limit, 100)))
    return [consent_event_response(event) for event in events]


@router.get("/households/{household_id}/consents/current", response_model=CurrentConsentResponse)
async def current_consents(
    household_id: str,
    session: SessionDep,
    _household: HouseholdDep,
) -> CurrentConsentResponse:
    events = await get_current_consents(session, household_id)
    return current_consent_response(events)


@router.get("/households/{household_id}/plans/accepted/latest", response_model=AcceptedPlanResponse | None)
async def latest_accepted_plan(
    household_id: str,
    session: SessionDep,
    _household: HouseholdDep,
) -> AcceptedPlanResponse | None:
    plan = await get_latest_accepted_plan(session, household_id)
    if plan is None:
        return None
    return accepted_plan_response(plan)


@router.post("/households/{household_id}/plans/approve", response_model=ApprovalEventResponse)
async def approve_plan(
    household_id: str,
    request: PlanApprovalRequest,
    session: SessionDep,
    _household: HouseholdDep,
) -> ApprovalEventResponse:
    event = await approve_plan_option(session, household_id=household_id, request=request)
    return approval_event_response(event)


@router.post("/households/{household_id}/shopping-list/decide", response_model=ApprovalEventResponse)
async def decide_shopping_list_item(
    household_id: str,
    request: ShoppingItemDecisionRequest,
    session: SessionDep,
    _household: HouseholdDep,
) -> ApprovalEventResponse:
    try:
        event = await decide_shopping_item(session, household_id=household_id, request=request)
    except IndexError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    except ValueError as exc:
        detail = str(exc)
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "not found" in detail.lower()
            else status.HTTP_422_UNPROCESSABLE_CONTENT
        )
        raise HTTPException(status_code, detail) from exc
    return approval_event_response(event)


@router.post("/households/{household_id}/plans/override", response_model=ApprovalEventResponse)
async def override_plan(
    household_id: str,
    request: PlanOverrideRequest,
    session: SessionDep,
    _household: HouseholdDep,
) -> ApprovalEventResponse:
    if not request.override_payload:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "override_payload is required")
    event = await override_plan_option(session, household_id=household_id, request=request)
    return approval_event_response(event)


@router.get("/households/demo", response_model=HouseholdResponse)
async def demo_household(session: SessionDep) -> HouseholdResponse:
    household = await get_or_create_demo_household(session)
    return household_response(household)


@router.get("/households/{household_id}/pantry", response_model=list[PantryLotResponse])
async def pantry_lots(
    household_id: str,
    session: SessionDep,
    _household: HouseholdDep,
) -> list[PantryLotResponse]:
    lots = await list_pantry_lots(session, household_id)
    return [pantry_lot_response(lot) for lot in lots]


@router.post("/households/{household_id}/pantry/confirm", response_model=list[PantryLotResponse])
async def confirm_pantry(
    household_id: str,
    request: PantryConfirmationRequest,
    session: SessionDep,
    _household: HouseholdDep,
) -> list[PantryLotResponse]:
    lots = await confirm_pantry_items(
        session,
        household_id=household_id,
        items=request.items,
        actor=request.actor,
        reason=request.reason,
    )
    return [pantry_lot_response(lot) for lot in lots]


@router.post("/households/{household_id}/purchases", response_model=PurchaseRecordResponse)
async def record_purchase(
    household_id: str,
    request: PurchaseEventCreateRequest,
    session: SessionDep,
    _household: HouseholdDep,
) -> PurchaseRecordResponse:
    try:
        event, pantry_lots = await record_purchase_event(
            session,
            household_id=household_id,
            request=request,
        )
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return purchase_record_response(event, pantry_lots)


@router.get("/households/{household_id}/purchases", response_model=list[PurchaseEventResponse])
async def purchases(
    household_id: str,
    session: SessionDep,
    _household: HouseholdDep,
    limit: int = 50,
) -> list[PurchaseEventResponse]:
    events = await list_purchase_events(session, household_id, max(1, min(limit, 100)))
    return [purchase_event_response(event) for event in events]


@router.get("/households/{household_id}/audit-events", response_model=list[AuditEventResponse])
async def audit_events(
    household_id: str,
    session: SessionDep,
    _household: HouseholdDep,
    limit: int = 50,
) -> list[AuditEventResponse]:
    events = await list_audit_events(session, household_id, max(1, min(limit, 100)))
    return [audit_event_response(event) for event in events]
