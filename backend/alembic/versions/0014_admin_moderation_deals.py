"""admin moderation and platform deals: retailer verification history, admin review fields, and discount scope/targets

Revision ID: 0014_admin_moderation_deals
Revises: 0013_retailer_inventory
Create Date: 2026-11-19 14:00:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0014_admin_moderation_deals"
down_revision: str | None = "0013_retailer_inventory"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Retailer review audit columns
    op.add_column(
        "retailers",
        sa.Column("reviewed_by_user_id", sa.Uuid(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_retailers_reviewed_by_user_id",
        "retailers",
        "users",
        ["reviewed_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "retailers",
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "retailers",
        sa.Column("rejection_reason", sa.Text(), nullable=True),
    )

    # 2. Retailer verification history table
    op.create_table(
        "retailer_verification_history",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("retailer_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("admin_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("from_status", sa.String(32), nullable=False),
        sa.Column("to_status", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["retailer_id"],
            ["retailers.id"],
            name="fk_ret_ver_hist_retailer_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["admin_id"],
            ["users.id"],
            name="fk_ret_ver_hist_admin_id",
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_retailer_verification_history_retailer_id",
        "retailer_verification_history",
        ["retailer_id"],
    )

    # 3. Platform deals and promotions extensions on discounts
    op.add_column(
        "discounts",
        sa.Column(
            "scope",
            sa.String(32),
            server_default=sa.text("'PLATFORM_WIDE'"),
            nullable=False,
        ),
    )
    op.create_index("ix_discounts_scope", "discounts", ["scope"])

    op.add_column(
        "discounts",
        sa.Column("category_id", sa.Uuid(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_discounts_category_id",
        "discounts",
        "categories",
        ["category_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_discounts_category_id", "discounts", ["category_id"])

    op.add_column(
        "discounts",
        sa.Column("product_id", sa.Uuid(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_discounts_product_id",
        "discounts",
        "products",
        ["product_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_discounts_product_id", "discounts", ["product_id"])

    op.add_column(
        "discounts",
        sa.Column("usage_limit", sa.Integer(), nullable=True),
    )
    op.add_column(
        "discounts",
        sa.Column(
            "times_used",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "discounts",
        sa.Column("description", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    # Drop discounts columns
    op.drop_column("discounts", "description")
    op.drop_column("discounts", "times_used")
    op.drop_column("discounts", "usage_limit")
    op.drop_index("ix_discounts_product_id", table_name="discounts")
    op.drop_constraint("fk_discounts_product_id", "discounts", type_="foreignkey")
    op.drop_column("discounts", "product_id")
    op.drop_index("ix_discounts_category_id", table_name="discounts")
    op.drop_constraint("fk_discounts_category_id", "discounts", type_="foreignkey")
    op.drop_column("discounts", "category_id")
    op.drop_index("ix_discounts_scope", table_name="discounts")
    op.drop_column("discounts", "scope")

    # Drop retailer verification history
    op.drop_index(
        "ix_retailer_verification_history_retailer_id",
        table_name="retailer_verification_history",
    )
    op.drop_table("retailer_verification_history")

    # Drop retailer review columns
    op.drop_column("retailers", "rejection_reason")
    op.drop_column("retailers", "verified_at")
    op.drop_constraint(
        "fk_retailers_reviewed_by_user_id", "retailers", type_="foreignkey"
    )
    op.drop_column("retailers", "reviewed_by_user_id")
