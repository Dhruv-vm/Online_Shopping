"""Phase 3E: Dukaan vs Dukaan (90-second reverse basket auctions)

Revision ID: 0030_dukaan_vs_dukaan
Revises: 0029_ai_negotiator
Create Date: 2026-11-20 23:15:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0030_dukaan_vs_dukaan"
down_revision: str | None = "0029_ai_negotiator"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "basket_auctions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "cart_id",
            sa.Uuid(),
            sa.ForeignKey("carts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "cart_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("reference_total_paise", sa.BigInteger(), nullable=False),
        sa.Column("pincode", sa.String(6), nullable=False),
        sa.Column(
            "duration_seconds", sa.Integer(), nullable=False, server_default="90"
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
        sa.Column("winning_bid_id", sa.Uuid(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_basket_auctions_live", "basket_auctions", ["status", "pincode", "ends_at"]
    )
    op.create_index("ix_basket_auctions_user", "basket_auctions", ["user_id", "status"])
    op.create_table(
        "basket_auction_bids",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "auction_id",
            sa.Uuid(),
            sa.ForeignKey("basket_auctions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "retailer_id",
            sa.Uuid(),
            sa.ForeignKey("retailers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("bid_price_paise", sa.BigInteger(), nullable=False),
        sa.Column("delivery_eta_minutes", sa.Integer(), nullable=False),
        sa.Column("warranty_note", sa.String(300), nullable=True),
        sa.Column(
            "line_allocation", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_auction_bids_rank",
        "basket_auction_bids",
        ["auction_id", "bid_price_paise", "delivery_eta_minutes"],
    )


def downgrade() -> None:
    op.drop_index("ix_auction_bids_rank", table_name="basket_auction_bids")
    op.drop_table("basket_auction_bids")
    op.drop_index("ix_basket_auctions_user", table_name="basket_auctions")
    op.drop_index("ix_basket_auctions_live", table_name="basket_auctions")
    op.drop_table("basket_auctions")
