"""Phase 3 foundation: price awards and retailer service PIN codes

Revision ID: 0022_marketplace_foundation
Revises: 0021_audit_missing_indexes
Create Date: 2026-11-20 21:30:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0022_marketplace_foundation"
down_revision: str | None = "0021_audit_missing_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "retailers",
        sa.Column(
            "service_pincodes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
    )
    op.create_table(
        "price_awards",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "customer_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "listing_id",
            sa.Uuid(),
            sa.ForeignKey("product_listings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("unit_price_paise", sa.BigInteger(), nullable=False),
        sa.Column("max_quantity", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quote_id", sa.Uuid(), nullable=True),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "unit_price_paise > 0", name="chk_price_award_price_positive"
        ),
        sa.CheckConstraint("max_quantity > 0", name="chk_price_award_qty_positive"),
    )
    op.create_index(
        "ix_price_awards_lookup",
        "price_awards",
        ["customer_id", "listing_id", "status"],
    )
    op.create_index("ix_price_awards_source", "price_awards", ["source", "source_id"])
    op.create_index("ix_price_awards_quote", "price_awards", ["quote_id"])


def downgrade() -> None:
    op.drop_index("ix_price_awards_quote", table_name="price_awards")
    op.drop_index("ix_price_awards_source", table_name="price_awards")
    op.drop_index("ix_price_awards_lookup", table_name="price_awards")
    op.drop_table("price_awards")
    op.drop_column("retailers", "service_pincodes")
