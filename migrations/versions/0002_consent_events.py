"""add consent events

Revision ID: 0002_consent_events
Revises: 0001_initial_schema
Create Date: 2026-06-09 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_consent_events"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "consent_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("household_id", sa.String(length=36), nullable=False),
        sa.Column("consent_type", sa.String(length=80), nullable=False),
        sa.Column("scope", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("actor", sa.String(length=80), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_consent_events_consent_type"), "consent_events", ["consent_type"], unique=False)
    op.create_index(op.f("ix_consent_events_household_id"), "consent_events", ["household_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_consent_events_household_id"), table_name="consent_events")
    op.drop_index(op.f("ix_consent_events_consent_type"), table_name="consent_events")
    op.drop_table("consent_events")
