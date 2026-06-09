"""add purchase events

Revision ID: 0003_purchase_events
Revises: 0002_consent_events
Create Date: 2026-06-09 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_purchase_events"
down_revision = "0002_consent_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchase_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("household_id", sa.String(length=36), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("accepted_plan_id", sa.String(length=36), nullable=True),
        sa.Column("shopping_decision_event_id", sa.String(length=36), nullable=True),
        sa.Column("actor", sa.String(length=80), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("total_cost", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("items_payload", sa.JSON(), nullable=False),
        sa.Column("pantry_lot_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_purchase_events_accepted_plan_id"),
        "purchase_events",
        ["accepted_plan_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_purchase_events_household_id"),
        "purchase_events",
        ["household_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_purchase_events_shopping_decision_event_id"),
        "purchase_events",
        ["shopping_decision_event_id"],
        unique=False,
    )
    op.create_index(op.f("ix_purchase_events_source"), "purchase_events", ["source"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_purchase_events_source"), table_name="purchase_events")
    op.drop_index(op.f("ix_purchase_events_shopping_decision_event_id"), table_name="purchase_events")
    op.drop_index(op.f("ix_purchase_events_household_id"), table_name="purchase_events")
    op.drop_index(op.f("ix_purchase_events_accepted_plan_id"), table_name="purchase_events")
    op.drop_table("purchase_events")
