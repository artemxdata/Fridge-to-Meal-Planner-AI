from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


def new_id() -> str:
    return str(uuid.uuid4())


def now_utc() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Household(Base):
    __tablename__ = "households"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    locale: Mapped[str] = mapped_column(String(10), nullable=False, default="ru")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)

    pantry_lots: Mapped[list[PantryLot]] = relationship(
        back_populates="household",
        cascade="all, delete-orphan",
    )
    observation_sessions: Mapped[list[ObservationSession]] = relationship(
        back_populates="household",
        cascade="all, delete-orphan",
    )
    approval_events: Mapped[list[ApprovalEvent]] = relationship(
        back_populates="household",
        cascade="all, delete-orphan",
    )
    accepted_plans: Mapped[list[AcceptedPlan]] = relationship(
        back_populates="household",
        cascade="all, delete-orphan",
    )
    audit_events: Mapped[list[AuditEvent]] = relationship(
        back_populates="household",
        cascade="all, delete-orphan",
    )
    consent_events: Mapped[list[ConsentEvent]] = relationship(
        back_populates="household",
        cascade="all, delete-orphan",
    )
    purchase_events: Mapped[list[PurchaseEvent]] = relationship(
        back_populates="household",
        cascade="all, delete-orphan",
    )


class PantryLot(Base):
    __tablename__ = "pantry_lots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    household_id: Mapped[str] = mapped_column(ForeignKey("households.id"), nullable=False, index=True)
    ingredient_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(30), nullable=False, default="шт")
    expires_in_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="confirmed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)

    household: Mapped[Household] = relationship(back_populates="pantry_lots")


class ObservationSession(Base):
    __tablename__ = "observation_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    household_id: Mapped[str] = mapped_column(ForeignKey("households.id"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    needs_confirmation: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)

    household: Mapped[Household] = relationship(back_populates="observation_sessions")
    candidates: Mapped[list[ObservationCandidate]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class ObservationCandidate(Base):
    __tablename__ = "observation_candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("observation_sessions.id"), nullable=False, index=True)
    household_id: Mapped[str] = mapped_column(ForeignKey("households.id"), nullable=False, index=True)
    ingredient_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(30), nullable=False, default="шт")
    expires_in_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="fallback")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)

    session: Mapped[ObservationSession] = relationship(back_populates="candidates")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    household_id: Mapped[str] = mapped_column(ForeignKey("households.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(80), nullable=False, default="demo-user")
    object_type: Mapped[str] = mapped_column(String(80), nullable=False)
    object_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)

    household: Mapped[Household] = relationship(back_populates="audit_events")


class ApprovalEvent(Base):
    __tablename__ = "approval_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    household_id: Mapped[str] = mapped_column(ForeignKey("households.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(80), nullable=False)
    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    proposal_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    approved_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    override_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)

    household: Mapped[Household] = relationship(back_populates="approval_events")


class AcceptedPlan(Base):
    __tablename__ = "accepted_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    household_id: Mapped[str] = mapped_column(ForeignKey("households.id"), nullable=False, index=True)
    source_approval_event_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    option_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    strategy: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    plan_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    shopping_list_payload: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)

    household: Mapped[Household] = relationship(back_populates="accepted_plans")


class ConsentEvent(Base):
    __tablename__ = "consent_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    household_id: Mapped[str] = mapped_column(ForeignKey("households.id"), nullable=False, index=True)
    consent_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(120), nullable=False, default="household")
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    actor: Mapped[str] = mapped_column(String(80), nullable=False, default="demo-user")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="user_action")
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)

    household: Mapped[Household] = relationship(back_populates="consent_events")


class PurchaseEvent(Base):
    __tablename__ = "purchase_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    household_id: Mapped[str] = mapped_column(ForeignKey("households.id"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    accepted_plan_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    shopping_decision_event_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    actor: Mapped[str] = mapped_column(String(80), nullable=False, default="demo-user")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    total_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="RUB")
    items_payload: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    pantry_lot_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)

    household: Mapped[Household] = relationship(back_populates="purchase_events")
