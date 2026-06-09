"""add consumption events

Revision ID: 0004_consumption_events
Revises: 0003_purchase_events
Create Date: 2026-06-09 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_consumption_events"
down_revision = "0003_purchase_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "consumption_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("household_id", sa.String(length=36), nullable=False),
        sa.Column("accepted_plan_id", sa.String(length=36), nullable=False),
        sa.Column("day", sa.Integer(), nullable=False),
        sa.Column("meal", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("servings", sa.Float(), nullable=False),
        sa.Column("actor", sa.String(length=80), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("recipe_title", sa.String(length=160), nullable=True),
        sa.Column("nutrition_payload", sa.JSON(), nullable=False),
        sa.Column("override_payload", sa.JSON(), nullable=False),
        sa.Column("consumed_at", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_consumption_events_accepted_plan_id"),
        "consumption_events",
        ["accepted_plan_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_consumption_events_household_id"),
        "consumption_events",
        ["household_id"],
        unique=False,
    )
    op.create_index(op.f("ix_consumption_events_meal"), "consumption_events", ["meal"], unique=False)
    op.create_index(op.f("ix_consumption_events_status"), "consumption_events", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_consumption_events_status"), table_name="consumption_events")
    op.drop_index(op.f("ix_consumption_events_meal"), table_name="consumption_events")
    op.drop_index(op.f("ix_consumption_events_household_id"), table_name="consumption_events")
    op.drop_index(op.f("ix_consumption_events_accepted_plan_id"), table_name="consumption_events")
    op.drop_table("consumption_events")
