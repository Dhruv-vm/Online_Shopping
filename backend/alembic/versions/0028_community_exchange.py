"""Phase 3C: Basket Community Exchange (customer RFQs and retailer bids)

Revision ID: 0028_community_exchange
Revises: 0027_community_buying
Create Date: 2026-11-20 22:45:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0028_community_exchange"
down_revision: str | None = "0027_community_buying"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "exchange_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("delivery_pincode", sa.String(6), nullable=False),
        sa.Column("budget_limit_paise", sa.BigInteger(), nullable=True),
        sa.Column(
            "items_manifest", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "status", sa.String(16), nullable=False, server_default="BIDDING_OPEN"
        ),
        sa.Column("accepted_bid_id", sa.Uuid(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_exchange_requests_open",
        "exchange_requests",
        ["status", "delivery_pincode", "expires_at"],
    )
    op.create_index(
        "ix_exchange_requests_user", "exchange_requests", ["user_id", "created_at"]
    )
    op.create_table(
        "exchange_bids",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "request_id",
            sa.Uuid(),
            sa.ForeignKey("exchange_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "retailer_id",
            sa.Uuid(),
            sa.ForeignKey("retailers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("bid_amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("estimated_delivery_hours", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "line_items", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("items_covered", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="SUBMITTED"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "request_id", "retailer_id", name="uq_exchange_bid_retailer"
        ),
    )


def downgrade() -> None:
    op.drop_table("exchange_bids")
    op.drop_index("ix_exchange_requests_user", table_name="exchange_requests")
    op.drop_index("ix_exchange_requests_open", table_name="exchange_requests")
    op.drop_table("exchange_requests")
