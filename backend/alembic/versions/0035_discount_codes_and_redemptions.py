"""Discount codes on quotes, applied discounts per quote line, and a
per-order discount redemption ledger (Version 2.0 Phase B, roadmap P0-2).

Additive only:
* ``checkout_quotes.discount_code`` — the normalised code that applied.
* ``checkout_quote_items.applied_discount_ids`` — discounts priced into the
  line (audit trail; drives usage counting at order creation).
* ``discount_redemptions`` — one row per (discount, order). RESERVED when the
  order is created (``discounts.times_used`` incremented under a row lock),
  RELEASED exactly once if the unpaid order is cancelled or expires.

Also indexes ``checkout_quotes.superseded_by_quote_id``: a pre-existing FK
without an index, flagged by scripts/verify-migrations.sh once
``checkout_quotes`` became one of the tables this revision touches.

``discounts.code`` already has a unique index (``ix_discounts_code``); codes
are looked up case-insensitively on a table of a few hundred rows at most, so
no extra index is added.

Revision ID: 0035_discount_codes_redemptions
Revises: 0034_foreign_key_indexes
Create Date: 2026-11-21 09:30:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0035_discount_codes_redemptions"
down_revision: str | None = "0034_foreign_key_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "checkout_quotes",
        sa.Column("discount_code", sa.String(50), nullable=True),
    )
    op.add_column(
        "checkout_quote_items",
        sa.Column(
            "applied_discount_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.create_table(
        "discount_redemptions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "discount_id",
            sa.Uuid(),
            sa.ForeignKey("discounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "order_id",
            sa.Uuid(),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="RESERVED"),
        sa.Column("release_reason", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "discount_id", "order_id", name="uq_discount_redemption_order"
        ),
        sa.CheckConstraint(
            "status IN ('RESERVED', 'RELEASED')",
            name="chk_discount_redemption_status",
        ),
    )
    op.create_index(
        "ix_discount_redemptions_order_id", "discount_redemptions", ["order_id"]
    )
    op.create_index(
        "ix_checkout_quotes_superseded_by_quote_id",
        "checkout_quotes",
        ["superseded_by_quote_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_checkout_quotes_superseded_by_quote_id", table_name="checkout_quotes"
    )
    op.drop_index("ix_discount_redemptions_order_id", table_name="discount_redemptions")
    op.drop_table("discount_redemptions")
    op.drop_column("checkout_quote_items", "applied_discount_ids")
    op.drop_column("checkout_quotes", "discount_code")
