"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-06-09 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "households",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("locale", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "accepted_plans",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("household_id", sa.String(length=36), nullable=False),
        sa.Column("source_approval_event_id", sa.String(length=36), nullable=False),
        sa.Column("option_id", sa.String(length=120), nullable=False),
        sa.Column("strategy", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("plan_payload", sa.JSON(), nullable=False),
        sa.Column("shopping_list_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_accepted_plans_household_id"), "accepted_plans", ["household_id"], unique=False)
    op.create_index(op.f("ix_accepted_plans_option_id"), "accepted_plans", ["option_id"], unique=False)
    op.create_index(
        op.f("ix_accepted_plans_source_approval_event_id"),
        "accepted_plans",
        ["source_approval_event_id"],
        unique=False,
    )

    op.create_table(
        "approval_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("household_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("actor", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("proposal_payload", sa.JSON(), nullable=False),
        sa.Column("approved_payload", sa.JSON(), nullable=False),
        sa.Column("override_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_approval_events_event_type"), "approval_events", ["event_type"], unique=False)
    op.create_index(
        op.f("ix_approval_events_household_id"), "approval_events", ["household_id"], unique=False
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("household_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("actor", sa.String(length=80), nullable=False),
        sa.Column("object_type", sa.String(length=80), nullable=False),
        sa.Column("object_id", sa.String(length=80), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_events_event_type"), "audit_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_audit_events_household_id"), "audit_events", ["household_id"], unique=False)

    op.create_table(
        "observation_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("household_id", sa.String(length=36), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("needs_confirmation", sa.Integer(), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_observation_sessions_household_id"), "observation_sessions", ["household_id"], unique=False
    )
    op.create_index(op.f("ix_observation_sessions_source"), "observation_sessions", ["source"], unique=False)

    op.create_table(
        "pantry_lots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("household_id", sa.String(length=36), nullable=False),
        sa.Column("ingredient_name", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=30), nullable=False),
        sa.Column("expires_in_days", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pantry_lots_household_id"), "pantry_lots", ["household_id"], unique=False)
    op.create_index(op.f("ix_pantry_lots_ingredient_name"), "pantry_lots", ["ingredient_name"], unique=False)

    op.create_table(
        "observation_candidates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("household_id", sa.String(length=36), nullable=False),
        sa.Column("ingredient_name", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=30), nullable=False),
        sa.Column("expires_in_days", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["observation_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_observation_candidates_household_id"),
        "observation_candidates",
        ["household_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_observation_candidates_ingredient_name"),
        "observation_candidates",
        ["ingredient_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_observation_candidates_session_id"), "observation_candidates", ["session_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_observation_candidates_session_id"), table_name="observation_candidates")
    op.drop_index(op.f("ix_observation_candidates_ingredient_name"), table_name="observation_candidates")
    op.drop_index(op.f("ix_observation_candidates_household_id"), table_name="observation_candidates")
    op.drop_table("observation_candidates")
    op.drop_index(op.f("ix_pantry_lots_ingredient_name"), table_name="pantry_lots")
    op.drop_index(op.f("ix_pantry_lots_household_id"), table_name="pantry_lots")
    op.drop_table("pantry_lots")
    op.drop_index(op.f("ix_observation_sessions_source"), table_name="observation_sessions")
    op.drop_index(op.f("ix_observation_sessions_household_id"), table_name="observation_sessions")
    op.drop_table("observation_sessions")
    op.drop_index(op.f("ix_audit_events_household_id"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_event_type"), table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index(op.f("ix_approval_events_household_id"), table_name="approval_events")
    op.drop_index(op.f("ix_approval_events_event_type"), table_name="approval_events")
    op.drop_table("approval_events")
    op.drop_index(op.f("ix_accepted_plans_source_approval_event_id"), table_name="accepted_plans")
    op.drop_index(op.f("ix_accepted_plans_option_id"), table_name="accepted_plans")
    op.drop_index(op.f("ix_accepted_plans_household_id"), table_name="accepted_plans")
    op.drop_table("accepted_plans")
    op.drop_table("households")
