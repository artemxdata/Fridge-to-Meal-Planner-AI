from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog import DEMO_PANTRY, normalize_name
from app.models import AuditEvent, Household, PantryLot
from app.schemas import AuditEventResponse, HouseholdResponse, PantryItem, PantryLotResponse

DEMO_HOUSEHOLD_ID = "demo-household"


def _iso(value) -> str:
    return value.isoformat(timespec="seconds")


def household_response(household: Household) -> HouseholdResponse:
    return HouseholdResponse(
        id=household.id,
        name=household.name,
        locale=household.locale,
        created_at=_iso(household.created_at),
    )


def pantry_lot_response(lot: PantryLot) -> PantryLotResponse:
    return PantryLotResponse(
        id=lot.id,
        household_id=lot.household_id,
        ingredient_name=lot.ingredient_name,
        display_name=lot.display_name,
        quantity=lot.quantity,
        unit=lot.unit,
        expires_in_days=lot.expires_in_days,
        source=lot.source,
        confidence=lot.confidence,
        status=lot.status,
        created_at=_iso(lot.created_at),
        updated_at=_iso(lot.updated_at),
    )


def audit_event_response(event: AuditEvent) -> AuditEventResponse:
    return AuditEventResponse(
        id=event.id,
        household_id=event.household_id,
        event_type=event.event_type,
        actor=event.actor,
        object_type=event.object_type,
        object_id=event.object_id,
        reason=event.reason,
        payload=event.payload,
        created_at=_iso(event.created_at),
    )


async def get_household(session: AsyncSession, household_id: str) -> Household | None:
    return await session.get(Household, household_id)


async def create_audit_event(
    session: AsyncSession,
    *,
    household_id: str,
    event_type: str,
    actor: str,
    object_type: str,
    object_id: str | None = None,
    reason: str = "",
    payload: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        household_id=household_id,
        event_type=event_type,
        actor=actor,
        object_type=object_type,
        object_id=object_id,
        reason=reason,
        payload=payload or {},
    )
    session.add(event)
    return event


async def get_or_create_demo_household(session: AsyncSession) -> Household:
    household = await session.get(Household, DEMO_HOUSEHOLD_ID)
    if household is None:
        household = Household(id=DEMO_HOUSEHOLD_ID, name="Demo household", locale="ru")
        session.add(household)
        await session.flush()
        await create_audit_event(
            session,
            household_id=household.id,
            event_type="household_created",
            actor="system",
            object_type="household",
            object_id=household.id,
            reason="created demo household",
        )

    existing_lots = await list_pantry_lots(session, household.id)
    if not existing_lots:
        await confirm_pantry_items(
            session,
            household_id=household.id,
            items=DEMO_PANTRY,
            actor="system",
            reason="seeded demo pantry",
        )
    await session.commit()
    return household


async def list_pantry_lots(session: AsyncSession, household_id: str) -> list[PantryLot]:
    result = await session.execute(
        select(PantryLot)
        .where(PantryLot.household_id == household_id)
        .order_by(PantryLot.created_at.desc(), PantryLot.display_name)
    )
    return list(result.scalars())


async def confirm_pantry_items(
    session: AsyncSession,
    *,
    household_id: str,
    items: list[PantryItem],
    actor: str,
    reason: str,
) -> list[PantryLot]:
    lots = []
    for item in items:
        lot = PantryLot(
            household_id=household_id,
            ingredient_name=normalize_name(item.name),
            display_name=item.name,
            quantity=item.quantity,
            unit=item.unit,
            expires_in_days=item.expires_in_days,
            source=item.source,
            confidence=item.confidence,
            status="confirmed",
        )
        session.add(lot)
        lots.append(lot)
    await session.flush()
    await create_audit_event(
        session,
        household_id=household_id,
        event_type="pantry_items_confirmed",
        actor=actor,
        object_type="pantry_lot_batch",
        reason=reason,
        payload={
            "items_count": len(lots),
            "lot_ids": [lot.id for lot in lots],
            "ingredient_names": [lot.ingredient_name for lot in lots],
        },
    )
    await session.commit()
    return lots


async def list_audit_events(session: AsyncSession, household_id: str, limit: int = 50) -> list[AuditEvent]:
    result = await session.execute(
        select(AuditEvent)
        .where(AuditEvent.household_id == household_id)
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars())
