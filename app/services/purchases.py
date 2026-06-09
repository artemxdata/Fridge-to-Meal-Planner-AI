from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog import normalize_name
from app.models import AcceptedPlan, ApprovalEvent, PantryLot, PurchaseEvent
from app.schemas import (
    PurchaseEventCreateRequest,
    PurchaseEventResponse,
    PurchaseRecordResponse,
)
from app.services.households import create_audit_event, pantry_lot_response


def _iso(value) -> str:
    return value.isoformat(timespec="seconds")


def purchase_event_response(event: PurchaseEvent) -> PurchaseEventResponse:
    return PurchaseEventResponse(
        id=event.id,
        household_id=event.household_id,
        source=event.source,
        accepted_plan_id=event.accepted_plan_id,
        shopping_decision_event_id=event.shopping_decision_event_id,
        actor=event.actor,
        reason=event.reason,
        total_cost=event.total_cost,
        currency=event.currency,
        items_payload=event.items_payload,
        pantry_lot_ids=event.pantry_lot_ids,
        created_at=_iso(event.created_at),
    )


def purchase_record_response(
    event: PurchaseEvent,
    pantry_lots: list[PantryLot],
) -> PurchaseRecordResponse:
    return PurchaseRecordResponse(
        event=purchase_event_response(event),
        pantry_lots=[pantry_lot_response(lot) for lot in pantry_lots],
        assistant_boundary=(
            "Purchase records are user-confirmed facts. They add confirmed pantry lots only after "
            "an explicit user action."
        ),
    )


async def _validate_accepted_plan(
    session: AsyncSession,
    *,
    household_id: str,
    accepted_plan_id: str,
) -> None:
    result = await session.execute(
        select(AcceptedPlan).where(
            AcceptedPlan.household_id == household_id,
            AcceptedPlan.id == accepted_plan_id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise LookupError("Accepted plan not found")


async def _validate_shopping_decision(
    session: AsyncSession,
    *,
    household_id: str,
    shopping_decision_event_id: str,
) -> None:
    result = await session.execute(
        select(ApprovalEvent).where(
            ApprovalEvent.household_id == household_id,
            ApprovalEvent.id == shopping_decision_event_id,
            ApprovalEvent.target_type == "shopping_item",
        )
    )
    if result.scalar_one_or_none() is None:
        raise LookupError("Shopping decision event not found")


async def record_purchase_event(
    session: AsyncSession,
    *,
    household_id: str,
    request: PurchaseEventCreateRequest,
) -> tuple[PurchaseEvent, list[PantryLot]]:
    if request.accepted_plan_id:
        await _validate_accepted_plan(
            session,
            household_id=household_id,
            accepted_plan_id=request.accepted_plan_id,
        )
    if request.shopping_decision_event_id:
        await _validate_shopping_decision(
            session,
            household_id=household_id,
            shopping_decision_event_id=request.shopping_decision_event_id,
        )

    pantry_lots = []
    for item in request.items:
        lot = PantryLot(
            household_id=household_id,
            ingredient_name=normalize_name(item.name),
            display_name=item.name,
            quantity=item.quantity,
            unit=item.unit,
            expires_in_days=item.expires_in_days,
            source=f"purchase:{request.source}",
            confidence=item.confidence,
            status="confirmed",
        )
        session.add(lot)
        pantry_lots.append(lot)
    await session.flush()

    event = PurchaseEvent(
        household_id=household_id,
        source=request.source,
        accepted_plan_id=request.accepted_plan_id,
        shopping_decision_event_id=request.shopping_decision_event_id,
        actor=request.actor,
        reason=request.reason,
        total_cost=request.total_cost,
        currency=request.currency,
        items_payload=[item.model_dump() for item in request.items],
        pantry_lot_ids=[lot.id for lot in pantry_lots],
    )
    session.add(event)
    await session.flush()
    await create_audit_event(
        session,
        household_id=household_id,
        event_type="purchase_recorded",
        actor=request.actor,
        object_type="purchase_event",
        object_id=event.id,
        reason=request.reason,
        payload={
            "purchase_event_id": event.id,
            "source": event.source,
            "items_count": len(pantry_lots),
            "pantry_lot_ids": [lot.id for lot in pantry_lots],
            "accepted_plan_id": request.accepted_plan_id,
            "shopping_decision_event_id": request.shopping_decision_event_id,
            "total_cost": request.total_cost,
            "currency": request.currency,
        },
    )
    await session.commit()
    return event, pantry_lots


async def list_purchase_events(
    session: AsyncSession,
    household_id: str,
    limit: int = 50,
) -> list[PurchaseEvent]:
    result = await session.execute(
        select(PurchaseEvent)
        .where(PurchaseEvent.household_id == household_id)
        .order_by(PurchaseEvent.created_at.desc(), PurchaseEvent.id.desc())
        .limit(limit)
    )
    return list(result.scalars())
