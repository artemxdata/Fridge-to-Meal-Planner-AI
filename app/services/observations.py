from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.catalog import normalize_name
from app.models import ObservationCandidate, ObservationSession, PantryLot, now_utc
from app.schemas import (
    ObservationConfirmRequest,
    ObservationSessionCreateRequest,
    ObservationSessionResponse,
)
from app.services.households import create_audit_event


def _iso(value) -> str | None:
    return value.isoformat(timespec="seconds") if value is not None else None


def observation_session_response(session: ObservationSession) -> ObservationSessionResponse:
    return ObservationSessionResponse(
        id=session.id,
        household_id=session.household_id,
        source=session.source,
        status=session.status,
        needs_confirmation=bool(session.needs_confirmation),
        raw_payload=session.raw_payload,
        candidates=[
            {
                "id": candidate.id,
                "session_id": candidate.session_id,
                "household_id": candidate.household_id,
                "ingredient_name": candidate.ingredient_name,
                "display_name": candidate.display_name,
                "quantity": candidate.quantity,
                "unit": candidate.unit,
                "expires_in_days": candidate.expires_in_days,
                "source": candidate.source,
                "confidence": candidate.confidence,
                "reason": candidate.reason,
                "status": candidate.status,
                "created_at": _iso(candidate.created_at),
                "updated_at": _iso(candidate.updated_at),
                "confirmed_at": _iso(candidate.confirmed_at),
            }
            for candidate in sorted(
                session.candidates,
                key=lambda item: (_iso(item.created_at) or "", item.id),
            )
        ],
        created_at=_iso(session.created_at),
        updated_at=_iso(session.updated_at),
    )


async def get_observation_session(
    session: AsyncSession,
    household_id: str,
    observation_id: str,
) -> ObservationSession | None:
    result = await session.execute(
        select(ObservationSession)
        .options(selectinload(ObservationSession.candidates))
        .where(
            ObservationSession.household_id == household_id,
            ObservationSession.id == observation_id,
        )
    )
    return result.scalar_one_or_none()


async def list_observation_sessions(
    session: AsyncSession,
    household_id: str,
    limit: int = 20,
) -> list[ObservationSession]:
    result = await session.execute(
        select(ObservationSession)
        .options(selectinload(ObservationSession.candidates))
        .where(ObservationSession.household_id == household_id)
        .order_by(ObservationSession.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars())


async def create_observation_session(
    session: AsyncSession,
    *,
    household_id: str,
    request: ObservationSessionCreateRequest,
) -> ObservationSession:
    observation = ObservationSession(
        household_id=household_id,
        source=request.source,
        status="pending",
        needs_confirmation=1,
        raw_payload=request.raw_payload,
    )
    session.add(observation)
    await session.flush()

    for item in request.candidates:
        candidate = ObservationCandidate(
            session_id=observation.id,
            household_id=household_id,
            ingredient_name=normalize_name(item.name),
            display_name=item.name,
            quantity=item.quantity,
            unit=item.unit,
            expires_in_days=item.expires_in_days,
            source=item.source,
            confidence=item.confidence,
            reason=item.reason,
            status="pending",
        )
        session.add(candidate)
    await session.flush()
    await create_audit_event(
        session,
        household_id=household_id,
        event_type="observation_session_created",
        actor=request.actor,
        object_type="observation_session",
        object_id=observation.id,
        reason=request.reason,
        payload={
            "source": observation.source,
            "candidates_count": len(request.candidates),
            "needs_confirmation": True,
        },
    )
    await session.commit()
    return await get_observation_session(session, household_id, observation.id) or observation


async def confirm_observation_candidates(
    session: AsyncSession,
    *,
    household_id: str,
    observation_id: str,
    request: ObservationConfirmRequest,
) -> tuple[ObservationSession, list[PantryLot]]:
    observation = await get_observation_session(session, household_id, observation_id)
    if observation is None:
        raise LookupError("Observation session not found")

    candidate_map = {candidate.id: candidate for candidate in observation.candidates}
    lots = []
    now = now_utc()
    for confirmation in request.candidates:
        candidate = candidate_map.get(confirmation.candidate_id)
        if candidate is None:
            raise ValueError(f"Candidate does not belong to observation: {confirmation.candidate_id}")
        if candidate.status == "confirmed":
            raise ValueError(f"Candidate is already confirmed: {confirmation.candidate_id}")

        item = confirmation.item
        lot = PantryLot(
            household_id=household_id,
            ingredient_name=normalize_name(item.name),
            display_name=item.name,
            quantity=item.quantity,
            unit=item.unit,
            expires_in_days=item.expires_in_days,
            source=f"observation:{observation.source}",
            confidence=item.confidence,
            status="confirmed",
        )
        session.add(lot)
        lots.append(lot)

        candidate.ingredient_name = normalize_name(item.name)
        candidate.display_name = item.name
        candidate.quantity = item.quantity
        candidate.unit = item.unit
        candidate.expires_in_days = item.expires_in_days
        candidate.confidence = item.confidence if item.confidence is not None else candidate.confidence
        candidate.status = "confirmed"
        candidate.confirmed_at = now
        candidate.updated_at = now

    await session.flush()
    statuses = {candidate.status for candidate in observation.candidates}
    observation.status = "confirmed" if statuses == {"confirmed"} else "partially_confirmed"
    observation.updated_at = now
    await create_audit_event(
        session,
        household_id=household_id,
        event_type="observation_candidates_confirmed",
        actor=request.actor,
        object_type="observation_session",
        object_id=observation.id,
        reason=request.reason,
        payload={
            "source": observation.source,
            "candidate_ids": [item.candidate_id for item in request.candidates],
            "lot_ids": [lot.id for lot in lots],
            "status": observation.status,
        },
    )
    await session.commit()
    refreshed = await get_observation_session(session, household_id, observation_id)
    return refreshed or observation, lots
