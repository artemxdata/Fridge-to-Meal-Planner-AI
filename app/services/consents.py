from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ConsentEvent
from app.schemas import ConsentEventCreateRequest, ConsentEventResponse, CurrentConsentResponse
from app.services.households import create_audit_event


def _iso(value) -> str:
    return value.isoformat(timespec="seconds")


def consent_event_response(event: ConsentEvent) -> ConsentEventResponse:
    return ConsentEventResponse(
        id=event.id,
        household_id=event.household_id,
        consent_type=event.consent_type,
        scope=event.scope,
        status=event.status,
        actor=event.actor,
        reason=event.reason,
        policy_version=event.policy_version,
        source=event.source,
        payload=event.payload,
        created_at=_iso(event.created_at),
    )


def current_consent_response(events: list[ConsentEvent]) -> CurrentConsentResponse:
    return CurrentConsentResponse(
        consents=[consent_event_response(event) for event in events],
        assistant_boundary=(
            "Consent state is derived from append-only user decisions. "
            "Private photos, receipts, and feedback must not be retained or used for training "
            "unless active consent permits it."
        ),
    )


async def create_consent_event(
    session: AsyncSession,
    *,
    household_id: str,
    request: ConsentEventCreateRequest,
) -> ConsentEvent:
    event = ConsentEvent(
        household_id=household_id,
        consent_type=request.consent_type,
        scope=request.scope,
        status=request.status,
        actor=request.actor,
        reason=request.reason,
        policy_version=request.policy_version,
        source=request.source,
        payload=request.payload,
    )
    session.add(event)
    await session.flush()
    await create_audit_event(
        session,
        household_id=household_id,
        event_type=f"consent_{request.status}",
        actor=request.actor,
        object_type="consent_event",
        object_id=event.id,
        reason=request.reason,
        payload={
            "consent_event_id": event.id,
            "consent_type": event.consent_type,
            "scope": event.scope,
            "status": event.status,
            "policy_version": event.policy_version,
        },
    )
    await session.commit()
    return event


async def list_consent_events(
    session: AsyncSession,
    household_id: str,
    limit: int = 50,
) -> list[ConsentEvent]:
    result = await session.execute(
        select(ConsentEvent)
        .where(ConsentEvent.household_id == household_id)
        .order_by(ConsentEvent.created_at.desc(), ConsentEvent.id.desc())
        .limit(limit)
    )
    return list(result.scalars())


async def get_current_consents(session: AsyncSession, household_id: str) -> list[ConsentEvent]:
    events = await list_consent_events(session, household_id, limit=500)
    latest_by_scope: dict[tuple[str, str], ConsentEvent] = {}
    for event in events:
        key = (event.consent_type, event.scope)
        if key not in latest_by_scope:
            latest_by_scope[key] = event
    return sorted(latest_by_scope.values(), key=lambda event: (event.consent_type, event.scope))
