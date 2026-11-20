"""Phase 3A: Demand Gap & Unmet Demand Aggregation

Revision ID: 0026_demand_gap
Revises: 0025_bharat_multilingual
Create Date: 2026-11-20 22:15:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0026_demand_gap"
down_revision: str | None = "0025_bharat_multilingual"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "demand_pools",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("normalized_product_name", sa.String(160), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column(
            "category_id",
            sa.Uuid(),
            sa.ForeignKey("categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("pincode", sa.String(6), nullable=True),
        sa.Column(
            "total_demand_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "unique_users_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "visibility_threshold", sa.Integer(), nullable=False, server_default="2"
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="OPEN"),
        sa.Column("last_signal_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fulfilled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_demand_pools_key",
        "demand_pools",
        ["normalized_product_name", "pincode", "status"],
    )
    op.create_index(
        "ix_demand_pools_status_activity", "demand_pools", ["status", "last_signal_at"]
    )
    # At most one OPEN pool per (product name, pincode); prevents concurrent duplicates.
    op.execute(
        "CREATE UNIQUE INDEX uq_demand_pool_open ON demand_pools "
        "(normalized_product_name, COALESCE(pincode, '')) WHERE status = 'OPEN'"
    )
    op.create_table(
        "demand_signals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "pool_id",
            sa.Uuid(),
            sa.ForeignKey("demand_pools.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("guest_token_hash", sa.String(64), nullable=True),
        sa.Column("query_text", sa.String(200), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        sa.Column(
            "listing_id",
            sa.Uuid(),
            sa.ForeignKey("product_listings.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("pincode", sa.String(6), nullable=True),
        sa.Column("signal_type", sa.String(16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_demand_signals_pool_user", "demand_signals", ["pool_id", "user_id"]
    )
    op.create_index(
        "ix_demand_signals_pool_guest",
        "demand_signals",
        ["pool_id", "guest_token_hash"],
    )
    op.create_index("ix_demand_signals_created", "demand_signals", ["created_at"])
    op.create_table(
        "demand_pool_responses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "pool_id",
            sa.Uuid(),
            sa.ForeignKey("demand_pools.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "retailer_id",
            sa.Uuid(),
            sa.ForeignKey("retailers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "listing_id",
            sa.Uuid(),
            sa.ForeignKey("product_listings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("offered_price_paise", sa.BigInteger(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "pool_id", "retailer_id", name="uq_demand_response_retailer"
        ),
    )


def downgrade() -> None:
    op.drop_table("demand_pool_responses")
    op.drop_index("ix_demand_signals_created", table_name="demand_signals")
    op.drop_index("ix_demand_signals_pool_guest", table_name="demand_signals")
    op.drop_index("ix_demand_signals_pool_user", table_name="demand_signals")
    op.drop_table("demand_signals")
    op.execute("DROP INDEX IF EXISTS uq_demand_pool_open")
    op.drop_index("ix_demand_pools_status_activity", table_name="demand_pools")
    op.drop_index("ix_demand_pools_key", table_name="demand_pools")
    op.drop_table("demand_pools")
