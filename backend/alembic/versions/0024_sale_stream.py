"""Phase 3G: Sale Stream live deal events (no Rewind)

Revision ID: 0024_sale_stream
Revises: 0023_price_intelligence
Create Date: 2026-11-20 21:45:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0024_sale_stream"
down_revision: str | None = "0023_price_intelligence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sale_stream_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("event_type", sa.String(16), nullable=False),
        sa.Column(
            "listing_id",
            sa.Uuid(),
            sa.ForeignKey("product_listings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "retailer_id",
            sa.Uuid(),
            sa.ForeignKey("retailers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "discount_id",
            sa.Uuid(),
            sa.ForeignKey("discounts.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("old_price_paise", sa.BigInteger(), nullable=False),
        sa.Column("flash_price_paise", sa.BigInteger(), nullable=False),
        sa.Column("stock_remaining", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("units_sold_24h", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_sale_stream_live",
        "sale_stream_events",
        ["status", "expires_at", "created_at"],
    )
    op.create_index(
        "ix_sale_stream_listing",
        "sale_stream_events",
        ["listing_id", "event_type", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_sale_stream_listing", table_name="sale_stream_events")
    op.drop_index("ix_sale_stream_live", table_name="sale_stream_events")
    op.drop_table("sale_stream_events")
