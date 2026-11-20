"""Phase 3F: Basket Price Intelligence (daily price history ticks)

Revision ID: 0023_price_intelligence
Revises: 0022_marketplace_foundation
Create Date: 2026-11-20 21:40:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0023_price_intelligence"
down_revision: str | None = "0022_marketplace_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "price_history_ticks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "listing_id",
            sa.Uuid(),
            sa.ForeignKey("product_listings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("recorded_date", sa.Date(), nullable=False),
        sa.Column("selling_price_paise", sa.BigInteger(), nullable=False),
        sa.Column("day_low_paise", sa.BigInteger(), nullable=False),
        sa.Column("mrp_paise", sa.BigInteger(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "listing_id", "recorded_date", name="uq_price_tick_listing_day"
        ),
    )
    op.create_index(
        "ix_price_ticks_listing_date",
        "price_history_ticks",
        ["listing_id", "recorded_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_price_ticks_listing_date", table_name="price_history_ticks")
    op.drop_table("price_history_ticks")
