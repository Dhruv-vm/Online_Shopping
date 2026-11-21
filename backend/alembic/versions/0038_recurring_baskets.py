"""Basket Monthly Essentials — recurring baskets (final cycle, Part 8).

Two new tables, no payment data:
* ``recurring_baskets`` — schedule (day 1..28, start/end), item snapshot,
  delivery address, status, skipped dates and the next scheduled date.
* ``recurring_basket_runs`` — one pre-order check per (basket, date); unique so
  the scheduler can never prepare the same date twice.

Revision ID: 0038_recurring_baskets
Revises: 0037_group_buy_invites
Create Date: 2026-11-21 16:30:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0038_recurring_baskets"
down_revision: str | None = "0037_group_buy_invites"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = postgresql.JSONB(astext_type=sa.Text())


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "recurring_baskets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "customer_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("items", JSONB, nullable=False),
        sa.Column("day_of_month", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column(
            "delivery_address_id",
            sa.Uuid(),
            sa.ForeignKey("addresses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column(
            "skip_dates", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("next_run_date", sa.Date(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "day_of_month BETWEEN 1 AND 28", name="ck_recurring_baskets_day"
        ),
    )
    op.create_index(
        "ix_recurring_baskets_customer_id", "recurring_baskets", ["customer_id"]
    )
    op.create_index(
        "ix_recurring_baskets_delivery_address_id",
        "recurring_baskets",
        ["delivery_address_id"],
    )
    op.create_index(
        "ix_recurring_baskets_next_run_date", "recurring_baskets", ["next_run_date"]
    )
    op.create_table(
        "recurring_basket_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "recurring_basket_id",
            sa.Uuid(),
            sa.ForeignKey("recurring_baskets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scheduled_for", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("check", JSONB, nullable=True),
        *_timestamps(),
        sa.UniqueConstraint(
            "recurring_basket_id", "scheduled_for", name="uq_recurring_basket_run_date"
        ),
    )
    op.create_index(
        "ix_recurring_basket_runs_recurring_basket_id",
        "recurring_basket_runs",
        ["recurring_basket_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_recurring_basket_runs_recurring_basket_id",
        table_name="recurring_basket_runs",
    )
    op.drop_table("recurring_basket_runs")
    op.drop_index("ix_recurring_baskets_next_run_date", table_name="recurring_baskets")
    op.drop_index(
        "ix_recurring_baskets_delivery_address_id", table_name="recurring_baskets"
    )
    op.drop_index("ix_recurring_baskets_customer_id", table_name="recurring_baskets")
    op.drop_table("recurring_baskets")
