from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AcceptedPlan, ApprovalEvent, now_utc
from app.schemas import (
    AcceptedPlanResponse,
    ApprovalEventResponse,
    PlanApprovalRequest,
    PlanOverrideRequest,
    ShoppingItemDecisionRequest,
)
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


def accepted_plan_response(plan: AcceptedPlan) -> AcceptedPlanResponse:
    return AcceptedPlanResponse(
        id=plan.id,
        household_id=plan.household_id,
        source_approval_event_id=plan.source_approval_event_id,
        option_id=plan.option_id,
        strategy=plan.strategy,
        title=plan.title,
        status=plan.status,
        plan_payload=plan.plan_payload,
        shopping_list_payload=plan.shopping_list_payload,
        created_at=_iso(plan.created_at),
        updated_at=_iso(plan.updated_at),
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
    await session.execute(
        update(AcceptedPlan)
        .where(AcceptedPlan.household_id == household_id, AcceptedPlan.status == "active")
        .values(status="superseded", updated_at=now_utc())
    )
    accepted_plan = AcceptedPlan(
        household_id=household_id,
        source_approval_event_id=event.id,
        option_id=request.option.option_id,
        strategy=request.option.strategy,
        title=request.option.title,
        plan_payload=request.option.plan,
        shopping_list_payload=request.option.plan.get("shopping_list", []),
    )
    session.add(accepted_plan)
    await session.flush()
    event.approved_payload = {
        **event.approved_payload,
        "accepted_plan_id": accepted_plan.id,
        "accepted_plan_status": accepted_plan.status,
    }
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
            "accepted_plan_id": accepted_plan.id,
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


async def get_latest_accepted_plan(
    session: AsyncSession,
    household_id: str,
) -> AcceptedPlan | None:
    result = await session.execute(
        select(AcceptedPlan)
        .where(AcceptedPlan.household_id == household_id, AcceptedPlan.status == "active")
        .order_by(AcceptedPlan.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_accepted_plan(
    session: AsyncSession,
    household_id: str,
    accepted_plan_id: str,
) -> AcceptedPlan | None:
    result = await session.execute(
        select(AcceptedPlan).where(
            AcceptedPlan.household_id == household_id,
            AcceptedPlan.id == accepted_plan_id,
        )
    )
    return result.scalar_one_or_none()


async def decide_shopping_item(
    session: AsyncSession,
    *,
    household_id: str,
    request: ShoppingItemDecisionRequest,
) -> ApprovalEvent:
    accepted_plan = await get_accepted_plan(session, household_id, request.accepted_plan_id)
    if accepted_plan is None:
        raise ValueError("Accepted plan not found")
    shopping_list = accepted_plan.shopping_list_payload or []
    if request.item_index >= len(shopping_list):
        raise IndexError("Shopping item index out of range")
    if request.decision == "changed" and not request.override_payload:
        raise ValueError("override_payload is required for changed shopping items")

    item_payload = request.item_payload or shopping_list[request.item_index]
    event_type = f"shopping_item_{request.decision}"
    event = ApprovalEvent(
        household_id=household_id,
        event_type=event_type,
        actor=request.actor,
        target_type="shopping_item",
        target_id=f"{accepted_plan.id}:{request.item_index}",
        status=request.decision,
        reason=request.reason,
        proposal_payload={
            "accepted_plan_id": accepted_plan.id,
            "option_id": accepted_plan.option_id,
            "item_index": request.item_index,
            "item": item_payload,
        },
        approved_payload={
            "accepted_plan_id": accepted_plan.id,
            "item_index": request.item_index,
            "decision": request.decision,
            "item": item_payload,
        },
        override_payload=request.override_payload,
    )
    session.add(event)
    await session.flush()
    await create_audit_event(
        session,
        household_id=household_id,
        event_type=event_type,
        actor=request.actor,
        object_type="approval_event",
        object_id=event.id,
        reason=request.reason,
        payload={
            "approval_event_id": event.id,
            "accepted_plan_id": accepted_plan.id,
            "option_id": accepted_plan.option_id,
            "item_index": request.item_index,
            "decision": request.decision,
        },
    )
    await session.commit()
    return event
