"""create carts and cart_items tables

Revision ID: 0004_cart_schema
Revises: 0003_identity_schema
Create Date: 2026-11-17 00:25:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_cart_schema"
down_revision: str | None = "0003_identity_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Carts table
    op.create_table(
        "carts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("guest_token_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "status", sa.String(length=32), nullable=False, server_default="ACTIVE"
        ),
        sa.Column(
            "currency", sa.String(length=3), nullable=False, server_default="INR"
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(customer_id IS NOT NULL AND guest_token_hash IS NULL) OR (customer_id IS NULL AND guest_token_hash IS NOT NULL)",
            name="chk_cart_ownership",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'MERGED', 'ABANDONED', 'CONVERTED')",
            name="chk_cart_status",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_carts_customer_id"), "carts", ["customer_id"], unique=False
    )
    op.create_index(
        op.f("ix_carts_guest_token_hash"), "carts", ["guest_token_hash"], unique=True
    )
    op.create_index(op.f("ix_carts_status"), "carts", ["status"], unique=False)
    op.create_index(op.f("ix_carts_expires_at"), "carts", ["expires_at"], unique=False)
    op.create_index(
        "uq_cart_customer_active",
        "carts",
        ["customer_id", "currency"],
        unique=True,
        postgresql_where=sa.text("customer_id IS NOT NULL AND status = 'ACTIVE'"),
        sqlite_where=sa.text("customer_id IS NOT NULL AND status = 'ACTIVE'"),
    )

    # 2. Cart Items table
    op.create_table(
        "cart_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cart_id", sa.Uuid(), nullable=False),
        sa.Column("listing_id", sa.Uuid(), nullable=False),
        sa.Column("variant_id", sa.Uuid(), nullable=False),
        sa.Column("retailer_id", sa.Uuid(), nullable=False),
        sa.Column(
            "quantity", sa.Integer(), nullable=False, server_default=sa.text("1")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "quantity > 0 AND quantity <= 10",
            name="chk_cart_item_quantity",
        ),
        sa.ForeignKeyConstraint(
            ["cart_id"],
            ["carts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["listing_id"],
            ["product_listings.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["product_variants.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["retailer_id"],
            ["retailers.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_cart_items_cart_id"), "cart_items", ["cart_id"], unique=False
    )
    op.create_index(
        op.f("ix_cart_items_listing_id"), "cart_items", ["listing_id"], unique=False
    )
    op.create_index(
        op.f("ix_cart_items_variant_id"), "cart_items", ["variant_id"], unique=False
    )
    op.create_index(
        op.f("ix_cart_items_retailer_id"), "cart_items", ["retailer_id"], unique=False
    )
    op.create_index(
        "uq_cart_listing", "cart_items", ["cart_id", "listing_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index("uq_cart_listing", table_name="cart_items")
    op.drop_index(op.f("ix_cart_items_retailer_id"), table_name="cart_items")
    op.drop_index(op.f("ix_cart_items_variant_id"), table_name="cart_items")
    op.drop_index(op.f("ix_cart_items_listing_id"), table_name="cart_items")
    op.drop_index(op.f("ix_cart_items_cart_id"), table_name="cart_items")
    op.drop_table("cart_items")

    op.drop_index("uq_cart_customer_active", table_name="carts")
    op.drop_index(op.f("ix_carts_expires_at"), table_name="carts")
    op.drop_index(op.f("ix_carts_status"), table_name="carts")
    op.drop_index(op.f("ix_carts_guest_token_hash"), table_name="carts")
    op.drop_index(op.f("ix_carts_customer_id"), table_name="carts")
    op.drop_table("carts")
