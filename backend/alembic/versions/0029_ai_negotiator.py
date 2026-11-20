"""Phase 3D: AI Negotiator (retailer rules and negotiation sessions)

Revision ID: 0029_ai_negotiator
Revises: 0028_community_exchange
Create Date: 2026-11-20 23:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0029_ai_negotiator"
down_revision: str | None = "0028_community_exchange"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "retailer_negotiation_rules",
        sa.Column("id", sa.Uuid(), primary_key=True),
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
            nullable=True,
        ),
        sa.Column("min_floor_price_paise", sa.BigInteger(), nullable=True),
        sa.Column("max_auto_discount_bps", sa.Integer(), nullable=False),
        sa.Column("bundle_quantity_threshold", sa.Integer(), nullable=True),
        sa.Column(
            "bundle_extra_discount_bps",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "max_auto_discount_bps >= 0 AND max_auto_discount_bps <= 5000",
            name="chk_neg_max_discount",
        ),
        sa.CheckConstraint(
            "bundle_extra_discount_bps >= 0 AND bundle_extra_discount_bps <= 2000",
            name="chk_neg_bundle_discount",
        ),
    )
    op.create_index(
        "ix_negotiation_rules_retailer",
        "retailer_negotiation_rules",
        ["retailer_id", "listing_id", "is_active"],
    )
    # One storewide rule and one rule per listing per retailer.
    op.execute(
        "CREATE UNIQUE INDEX uq_negotiation_rule_scope ON retailer_negotiation_rules "
        "(retailer_id, COALESCE(listing_id, '00000000-0000-0000-0000-000000000000'::uuid))"
    )
    op.create_table(
        "negotiation_sessions",
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
        sa.Column("cart_fingerprint", sa.String(64), nullable=False),
        sa.Column("language", sa.String(8), nullable=False, server_default="en"),
        sa.Column("target_price_paise", sa.BigInteger(), nullable=True),
        sa.Column("max_budget_paise", sa.BigInteger(), nullable=True),
        sa.Column("list_total_paise", sa.BigInteger(), nullable=False),
        sa.Column("floor_total_paise", sa.BigInteger(), nullable=False),
        sa.Column("current_round", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_rounds", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("proposed_price_paise", sa.BigInteger(), nullable=False),
        sa.Column("final_accepted_price_paise", sa.BigInteger(), nullable=True),
        sa.Column("lines", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("messages", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "status", sa.String(16), nullable=False, server_default="IN_PROGRESS"
        ),
        sa.Column("quote_id", sa.Uuid(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_negotiation_sessions_user",
        "negotiation_sessions",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_negotiation_sessions_user", table_name="negotiation_sessions")
    op.drop_table("negotiation_sessions")
    op.execute("DROP INDEX IF EXISTS uq_negotiation_rule_scope")
    op.drop_index(
        "ix_negotiation_rules_retailer", table_name="retailer_negotiation_rules"
    )
    op.drop_table("retailer_negotiation_rules")
