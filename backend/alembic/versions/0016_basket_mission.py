"""Phase 2A: Basket Mission schema (shopping_missions and shopping_mission_items)

Revision ID: 0016_basket_mission
Revises: 0015_order_item_fulfillment
Create Date: 2026-11-20 06:15:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0016_basket_mission"
down_revision: str | None = "0015_order_item_fulfillment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    jsonb_type = postgresql.JSONB(astext_type=sa.Text()).with_variant(
        sa.JSON(), "sqlite"
    )

    # 1. Create shopping_missions table
    op.create_table(
        "shopping_missions",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "customer_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("budget_paise", sa.BigInteger(), nullable=False),
        sa.Column(
            "category_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("categories.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("people_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "preferences",
            jsonb_type,
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "excluded_brands",
            jsonb_type,
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(32),
            server_default="ACTIVE",
            nullable=False,
            index=True,
        ),
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
        sa.CheckConstraint(
            "budget_paise > 0", name="chk_shopping_mission_budget_positive"
        ),
        sa.CheckConstraint(
            "people_count >= 1", name="chk_shopping_mission_people_positive"
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'SAVED', 'COMPLETED', 'ARCHIVED')",
            name="chk_shopping_mission_status",
        ),
    )

    # 2. Create shopping_mission_items table
    op.create_table(
        "shopping_mission_items",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "mission_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("shopping_missions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "product_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "variant_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("product_variants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "listing_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("product_listings.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "retailer_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("retailers.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "group_name",
            sa.String(100),
            server_default="Essentials",
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("unit_price_paise", sa.Integer(), nullable=False),
        sa.Column(
            "is_selected",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column("recommendation_reason", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
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
        sa.CheckConstraint("quantity >= 1", name="chk_mission_item_quantity_positive"),
        sa.CheckConstraint(
            "unit_price_paise >= 0",
            name="chk_mission_item_unit_price_nonnegative",
        ),
    )


def downgrade() -> None:
    op.drop_table("shopping_mission_items")
    op.drop_table("shopping_missions")
