"""Phase 3B: Basket Community Buying (group purchasing)

Revision ID: 0027_community_buying
Revises: 0026_demand_gap
Create Date: 2026-11-20 22:30:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0027_community_buying"
down_revision: str | None = "0026_demand_gap"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "group_buy_campaigns",
        sa.Column("id", sa.Uuid(), primary_key=True),
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
            "created_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("min_participants", sa.Integer(), nullable=False),
        sa.Column("max_participants", sa.Integer(), nullable=False),
        sa.Column(
            "current_participants", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("total_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "max_quantity_per_member", sa.Integer(), nullable=False, server_default="5"
        ),
        sa.Column("discount_bps", sa.Integer(), nullable=False),
        sa.Column("list_price_paise", sa.BigInteger(), nullable=False),
        sa.Column("group_price_paise", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="OPEN"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("min_participants >= 2", name="chk_gb_min"),
        sa.CheckConstraint("max_participants >= min_participants", name="chk_gb_max"),
        sa.CheckConstraint(
            "current_participants >= 0 AND current_participants <= max_participants",
            name="chk_gb_current",
        ),
        sa.CheckConstraint(
            "discount_bps > 0 AND discount_bps <= 9000", name="chk_gb_discount"
        ),
        sa.CheckConstraint("group_price_paise > 0", name="chk_gb_price"),
    )
    op.create_index(
        "ix_group_buy_status_expiry", "group_buy_campaigns", ["status", "expires_at"]
    )
    op.create_index(
        "ix_group_buy_retailer", "group_buy_campaigns", ["retailer_id", "status"]
    )
    op.create_table(
        "group_buy_members",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "campaign_id",
            sa.Uuid(),
            sa.ForeignKey("group_buy_campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="JOINED"),
        sa.Column("award_id", sa.Uuid(), nullable=True),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("campaign_id", "user_id", name="uq_group_buy_member"),
        sa.CheckConstraint("quantity > 0", name="chk_gb_member_qty"),
    )
    op.create_index("ix_group_buy_members_award", "group_buy_members", ["award_id"])


def downgrade() -> None:
    op.drop_index("ix_group_buy_members_award", table_name="group_buy_members")
    op.drop_table("group_buy_members")
    op.drop_index("ix_group_buy_retailer", table_name="group_buy_campaigns")
    op.drop_index("ix_group_buy_status_expiry", table_name="group_buy_campaigns")
    op.drop_table("group_buy_campaigns")
