"""Marketplace completion: data quarantine ledger, labelled demo price history,
price alerts, customer-startable group buys.

Revision ID: 0031_marketplace_completion
Revises: 0030_dukaan_vs_dukaan
Create Date: 2026-11-20 23:30:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0031_marketplace_completion"
down_revision: str | None = "0030_dukaan_vs_dukaan"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "data_quarantine",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("batch_id", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(48), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column(
            "previous_state", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("restored_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_data_quarantine_batch", "data_quarantine", ["batch_id"])
    op.create_index(
        "ix_data_quarantine_entity", "data_quarantine", ["entity_type", "entity_id"]
    )

    op.add_column(
        "price_history_ticks",
        sa.Column(
            "source", sa.String(16), nullable=False, server_default=sa.text("'LIVE'")
        ),
    )
    op.create_check_constraint(
        "chk_price_tick_source",
        "price_history_ticks",
        "source IN ('LIVE', 'DEMO_SEED')",
    )

    op.create_table(
        "price_alerts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "variant_id",
            sa.Uuid(),
            sa.ForeignKey("product_variants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_price_paise", sa.BigInteger(), nullable=False),
        sa.Column(
            "status", sa.String(16), nullable=False, server_default=sa.text("'ACTIVE'")
        ),
        sa.Column(
            "triggered_listing_id",
            sa.Uuid(),
            sa.ForeignKey("product_listings.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("triggered_price_paise", sa.BigInteger(), nullable=True),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("target_price_paise > 0", name="chk_price_alert_target"),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'TRIGGERED', 'CANCELLED')",
            name="chk_price_alert_status",
        ),
    )
    op.create_index(
        "uq_price_alert_active",
        "price_alerts",
        ["user_id", "variant_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.create_index(
        "ix_price_alert_variant_status", "price_alerts", ["variant_id", "status"]
    )

    op.create_table(
        "group_buy_templates",
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
            nullable=False,
        ),
        sa.Column("min_participants", sa.Integer(), nullable=False),
        sa.Column("max_participants", sa.Integer(), nullable=False),
        sa.Column("discount_bps", sa.Integer(), nullable=False),
        sa.Column("duration_hours", sa.Integer(), nullable=False),
        sa.Column("max_quantity_per_member", sa.Integer(), nullable=False),
        sa.Column("max_open_campaigns", sa.Integer(), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("min_participants >= 2", name="chk_gbt_min"),
        sa.CheckConstraint("max_participants >= min_participants", name="chk_gbt_max"),
        sa.CheckConstraint(
            "discount_bps > 0 AND discount_bps <= 9000", name="chk_gbt_discount"
        ),
        sa.CheckConstraint("duration_hours BETWEEN 1 AND 336", name="chk_gbt_duration"),
        sa.CheckConstraint(
            "max_quantity_per_member BETWEEN 1 AND 10", name="chk_gbt_qty"
        ),
        sa.CheckConstraint("max_open_campaigns BETWEEN 1 AND 50", name="chk_gbt_open"),
    )
    op.create_index(
        "uq_group_buy_template_listing",
        "group_buy_templates",
        ["listing_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.add_column(
        "group_buy_campaigns",
        sa.Column(
            "template_id",
            sa.Uuid(),
            sa.ForeignKey("group_buy_templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("group_buy_campaigns", "template_id")
    op.drop_index("uq_group_buy_template_listing", table_name="group_buy_templates")
    op.drop_table("group_buy_templates")
    op.drop_index("ix_price_alert_variant_status", table_name="price_alerts")
    op.drop_index("uq_price_alert_active", table_name="price_alerts")
    op.drop_table("price_alerts")
    op.drop_constraint("chk_price_tick_source", "price_history_ticks", type_="check")
    op.drop_column("price_history_ticks", "source")
    op.drop_index("ix_data_quarantine_entity", table_name="data_quarantine")
    op.drop_index("ix_data_quarantine_batch", table_name="data_quarantine")
    op.drop_table("data_quarantine")
