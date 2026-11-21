"""Customer intent workflow (final cycle, Part 6).

Additive only, on ``customer_recurring_intentions``:
* ``items`` — what the customer asked for (name, quantity, specifications).
* ``pincode`` — the service area the intent is for.
* ``purchase_by`` — optional purchase timeframe.
* ``dedupe_key`` — hash of (items, pincode, frequency) so resubmitting the same
  intent updates the existing record instead of creating a duplicate.
* ``last_analysis`` / ``analyzed_at`` — the last matching result shown.

Revision ID: 0036_intent_workflow
Revises: 0035_discount_codes_redemptions
Create Date: 2026-11-21 14:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0036_intent_workflow"
down_revision: str | None = "0035_discount_codes_redemptions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "customer_recurring_intentions"


def upgrade() -> None:
    op.add_column(
        TABLE,
        sa.Column(
            "items",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(TABLE, sa.Column("pincode", sa.String(6), nullable=True))
    op.add_column(TABLE, sa.Column("purchase_by", sa.Date(), nullable=True))
    op.add_column(TABLE, sa.Column("dedupe_key", sa.String(64), nullable=True))
    op.add_column(
        TABLE,
        sa.Column(
            "last_analysis", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )
    op.add_column(
        TABLE, sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index(
        "ix_customer_recurring_intentions_customer_dedupe",
        TABLE,
        ["customer_id", "dedupe_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_customer_recurring_intentions_customer_dedupe", table_name=TABLE)
    for col in (
        "analyzed_at",
        "last_analysis",
        "dedupe_key",
        "purchase_by",
        "pincode",
        "items",
    ):
        op.drop_column(TABLE, col)
