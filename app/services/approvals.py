from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApprovalEvent
from app.schemas import ApprovalEventResponse, PlanApprovalRequest, PlanOverrideRequest
from app.services.households import create_audit_event


def _iso(value) -> str:
    return value.isoformat(timespec="seconds")


def approval_event_response(event: ApprovalEvent) -> ApprovalEventResponse:
    return ApprovalEventResponse(
        id=event.id,
        household_id=event.household_id,
        event_type=event.event_type,
        actor=event.actor,
        target_type=event.target_type,
        target_id=event.target_id,
        status=event.status,
        reason=event.reason,
        proposal_payload=event.proposal_payload,
        approved_payload=event.approved_payload,
        override_payload=event.override_payload,
        created_at=_iso(event.created_at),
    )


async def approve_plan_option(
    session: AsyncSession,
    *,
    household_id: str,
    request: PlanApprovalRequest,
) -> ApprovalEvent:
    option_payload = request.option.model_dump()
    event = ApprovalEvent(
        household_id=household_id,
        event_type="plan_option_approved",
        actor=request.actor,
        target_type="plan_option",
        target_id=request.option.option_id,
        status="approved",
        reason=request.reason,
        proposal_payload=option_payload,
        approved_payload={
            "option_id": request.option.option_id,
            "strategy": request.option.strategy,
            "plan": request.option.plan,
            "shopping_list": request.option.plan.get("shopping_list", []),
        },
    )
    session.add(event)
    await session.flush()
    await create_audit_event(
        session,
        household_id=household_id,
        event_type="plan_option_approved",
        actor=request.actor,
        object_type="approval_event",
        object_id=event.id,
        reason=request.reason,
        payload={
            "approval_event_id": event.id,
            "option_id": request.option.option_id,
            "strategy": request.option.strategy,
        },
    )
    await session.commit()
    return event


async def override_plan_option(
    session: AsyncSession,
    *,
    household_id: str,
    request: PlanOverrideRequest,
) -> ApprovalEvent:
    original_payload = request.original_option.model_dump()
    event = ApprovalEvent(
        household_id=household_id,
        event_type="plan_option_overridden",
        actor=request.actor,
        target_type="plan_option",
        target_id=request.original_option.option_id,
        status="overridden",
        reason=request.reason,
        proposal_payload=original_payload,
        approved_payload={
            "option_id": request.original_option.option_id,
            "strategy": request.original_option.strategy,
            "plan": request.original_option.plan,
            "shopping_list": request.original_option.plan.get("shopping_list", []),
        },
        override_payload=request.override_payload,
    )
    session.add(event)
    await session.flush()
    await create_audit_event(
        session,
        household_id=household_id,
        event_type="plan_option_overridden",
        actor=request.actor,
        object_type="approval_event",
        object_id=event.id,
        reason=request.reason,
        payload={
            "approval_event_id": event.id,
            "option_id": request.original_option.option_id,
            "strategy": request.original_option.strategy,
            "override_keys": sorted(request.override_payload),
        },
    )
    await session.commit()
    return event


async def list_approval_events(
    session: AsyncSession,
    household_id: str,
    limit: int = 50,
) -> list[ApprovalEvent]:
    result = await session.execute(
        select(ApprovalEvent)
        .where(ApprovalEvent.household_id == household_id)
        .order_by(ApprovalEvent.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars())
