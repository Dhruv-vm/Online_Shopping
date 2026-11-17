"""create discounts, checkout_quotes, and checkout_quote_items tables, add hsn and gst columns

Revision ID: 0005_pricing_quotes_schema
Revises: 0004_cart_schema
Create Date: 2026-11-17 14:30:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_pricing_quotes_schema"
down_revision: str | None = "0004_cart_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add HSN, GST, and provenance columns to product_listings (nullable without universal defaults)
    op.add_column(
        "product_listings",
        sa.Column("hsn_code", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "product_listings",
        sa.Column("gst_rate_basis_points", sa.Integer(), nullable=True),
    )
    op.add_column(
        "product_listings",
        sa.Column("tax_classification_source", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "product_listings",
        sa.Column(
            "is_tax_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # 2. Add state and provenance columns to retailers (nullable without universal defaults)
    op.add_column(
        "retailers",
        sa.Column("state", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "retailers",
        sa.Column("state_source", sa.String(length=64), nullable=True),
    )

    # Safe migration backfill: populate existing retailers with registered origin states
    op.execute(
        "UPDATE retailers SET state = 'MH', state_source = 'PROVISIONAL_SEED' WHERE slug IN ('reliance-digital', 'tata-cliq', 'natures-basket', 'crossword-bookstore');"
    )
    op.execute(
        "UPDATE retailers SET state = 'KA', state_source = 'PROVISIONAL_SEED' WHERE slug IN ('croma', 'decathlon-india');"
    )
    op.execute(
        "UPDATE retailers SET state = 'DL', state_source = 'PROVISIONAL_SEED' WHERE slug IN ('fabindia');"
    )
    op.execute(
        "UPDATE retailers SET state = 'KA', state_source = 'PROVISIONAL_SEED' WHERE state IS NULL;"
    )

    # Safe migration backfill: populate existing listings based on product category statutory classifications
    op.execute("""
        UPDATE product_listings pl
        SET hsn_code = CASE
            WHEN c.slug = 'electronics' THEN '8518'
            WHEN c.slug = 'fashion' THEN '6109'
            WHEN c.slug = 'groceries' THEN '1006'
            WHEN c.slug = 'beauty' THEN '3304'
            WHEN c.slug = 'home-furniture' THEN '9403'
            WHEN c.slug = 'sports-fitness' THEN '9506'
            WHEN c.slug = 'books-stationery' THEN '4901'
            ELSE NULL
        END,
        gst_rate_basis_points = CASE
            WHEN c.slug = 'electronics' THEN 1800
            WHEN c.slug = 'fashion' THEN 500
            WHEN c.slug = 'groceries' THEN 500
            WHEN c.slug = 'beauty' THEN 1800
            WHEN c.slug = 'home-furniture' THEN 1800
            WHEN c.slug = 'sports-fitness' THEN 1200
            WHEN c.slug = 'books-stationery' THEN 0
            ELSE NULL
        END,
        tax_classification_source = 'PROVISIONAL_SEED',
        is_tax_verified = true
        FROM product_variants pv
        JOIN products p ON pv.product_id = p.id
        JOIN categories c ON p.category_id = c.id
        WHERE pl.variant_id = pv.id AND pl.hsn_code IS NULL;
    """)

    # 3. Create discounts table
    op.create_table(
        "discounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "discount_type",
            sa.String(length=20),
            nullable=False,
            server_default="PERCENTAGE",
        ),
        sa.Column("discount_value", sa.Integer(), nullable=False),
        sa.Column("listing_id", sa.Uuid(), nullable=True),
        sa.Column(
            "min_order_paise",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("max_discount_paise", sa.BigInteger(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "valid_from",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint("discount_value > 0", name="chk_discount_value_positive"),
        sa.CheckConstraint(
            "discount_type IN ('PERCENTAGE', 'FIXED_AMOUNT')",
            name="chk_discount_type",
        ),
        sa.ForeignKeyConstraint(
            ["listing_id"],
            ["product_listings.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_discounts_code"), "discounts", ["code"], unique=True)
    op.create_index(
        op.f("ix_discounts_listing_id"), "discounts", ["listing_id"], unique=False
    )
    op.create_index(
        op.f("ix_discounts_is_active"), "discounts", ["is_active"], unique=False
    )

    # 4. Create checkout_quotes table
    op.create_table(
        "checkout_quotes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("guest_token_hash", sa.String(length=64), nullable=True),
        sa.Column("cart_id", sa.Uuid(), nullable=True),
        sa.Column("delivery_address_id", sa.Uuid(), nullable=True),
        sa.Column("delivery_state", sa.String(length=100), nullable=True),
        sa.Column("subtotal_paise", sa.BigInteger(), nullable=False),
        sa.Column(
            "discount_total_paise",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "delivery_fee_paise",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "cgst_paise",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "sgst_paise",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "igst_paise",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "total_tax_paise",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("total_payable_paise", sa.BigInteger(), nullable=False),
        sa.Column(
            "currency", sa.String(length=3), nullable=False, server_default="INR"
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column(
            "is_consumed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("superseded_by_quote_id", sa.Uuid(), nullable=True),
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
            "(customer_id IS NOT NULL AND guest_token_hash IS NULL) OR "
            "(customer_id IS NULL AND guest_token_hash IS NOT NULL)",
            name="chk_quote_ownership",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'CONSUMED', 'EXPIRED', 'SUPERSEDED')",
            name="chk_quote_status",
        ),
        sa.CheckConstraint("subtotal_paise >= 0", name="chk_quote_subtotal_positive"),
        sa.CheckConstraint(
            "discount_total_paise >= 0", name="chk_quote_discount_positive"
        ),
        sa.CheckConstraint(
            "delivery_fee_paise >= 0", name="chk_quote_delivery_fee_positive"
        ),
        sa.CheckConstraint("total_tax_paise >= 0", name="chk_quote_total_tax_positive"),
        sa.CheckConstraint(
            "total_payable_paise >= 0", name="chk_quote_payable_positive"
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["cart_id"],
            ["carts.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["delivery_address_id"],
            ["addresses.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["superseded_by_quote_id"],
            ["checkout_quotes.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_checkout_quotes_customer_id"),
        "checkout_quotes",
        ["customer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_checkout_quotes_guest_token_hash"),
        "checkout_quotes",
        ["guest_token_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_checkout_quotes_cart_id"),
        "checkout_quotes",
        ["cart_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_checkout_quotes_delivery_address_id"),
        "checkout_quotes",
        ["delivery_address_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_checkout_quotes_expires_at"),
        "checkout_quotes",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_quotes_customer_active",
        "checkout_quotes",
        ["customer_id", "status"],
        unique=False,
        postgresql_where=sa.text("customer_id IS NOT NULL AND status = 'ACTIVE'"),
    )
    op.create_index(
        "ix_quotes_guest_active",
        "checkout_quotes",
        ["guest_token_hash", "status"],
        unique=False,
        postgresql_where=sa.text("guest_token_hash IS NOT NULL AND status = 'ACTIVE'"),
    )

    # 5. Create checkout_quote_items table
    op.create_table(
        "checkout_quote_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("quote_id", sa.Uuid(), nullable=False),
        sa.Column("listing_id", sa.Uuid(), nullable=False),
        sa.Column("variant_id", sa.Uuid(), nullable=False),
        sa.Column("retailer_id", sa.Uuid(), nullable=False),
        sa.Column("product_title", sa.String(length=255), nullable=False),
        sa.Column("variant_title", sa.String(length=255), nullable=False),
        sa.Column("sku", sa.String(length=100), nullable=True),
        sa.Column("hsn_code", sa.String(length=16), nullable=False),
        sa.Column("gst_rate_basis_points", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_original_price_paise", sa.BigInteger(), nullable=False),
        sa.Column("unit_selling_price_paise", sa.BigInteger(), nullable=False),
        sa.Column(
            "unit_discount_paise",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("unit_discounted_price_paise", sa.BigInteger(), nullable=False),
        sa.Column("total_selling_price_paise", sa.BigInteger(), nullable=False),
        sa.Column("taxable_base_paise", sa.BigInteger(), nullable=False),
        sa.Column(
            "cgst_paise",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "sgst_paise",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "igst_paise",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "total_tax_paise",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("retailer_name", sa.String(length=255), nullable=False),
        sa.Column("retailer_state", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("quantity > 0", name="chk_quote_item_quantity_positive"),
        sa.CheckConstraint(
            "unit_original_price_paise >= 0",
            name="chk_quote_item_original_price_positive",
        ),
        sa.CheckConstraint(
            "unit_selling_price_paise >= 0",
            name="chk_quote_item_selling_price_positive",
        ),
        sa.CheckConstraint(
            "unit_discounted_price_paise >= 0",
            name="chk_quote_item_discounted_price_positive",
        ),
        sa.CheckConstraint(
            "taxable_base_paise >= 0",
            name="chk_quote_item_taxable_base_positive",
        ),
        sa.ForeignKeyConstraint(
            ["listing_id"],
            ["product_listings.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["quote_id"],
            ["checkout_quotes.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["retailer_id"],
            ["retailers.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["product_variants.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_checkout_quote_items_quote_id"),
        "checkout_quote_items",
        ["quote_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_checkout_quote_items_listing_id"),
        "checkout_quote_items",
        ["listing_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_checkout_quote_items_variant_id"),
        "checkout_quote_items",
        ["variant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_checkout_quote_items_retailer_id"),
        "checkout_quote_items",
        ["retailer_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_checkout_quote_items_retailer_id"),
        table_name="checkout_quote_items",
    )
    op.drop_index(
        op.f("ix_checkout_quote_items_variant_id"),
        table_name="checkout_quote_items",
    )
    op.drop_index(
        op.f("ix_checkout_quote_items_listing_id"),
        table_name="checkout_quote_items",
    )
    op.drop_index(
        op.f("ix_checkout_quote_items_quote_id"),
        table_name="checkout_quote_items",
    )
    op.drop_table("checkout_quote_items")

    op.drop_index("ix_quotes_guest_active", table_name="checkout_quotes")
    op.drop_index("ix_quotes_customer_active", table_name="checkout_quotes")
    op.drop_index(op.f("ix_checkout_quotes_expires_at"), table_name="checkout_quotes")
    op.drop_index(
        op.f("ix_checkout_quotes_delivery_address_id"),
        table_name="checkout_quotes",
    )
    op.drop_index(op.f("ix_checkout_quotes_cart_id"), table_name="checkout_quotes")
    op.drop_index(
        op.f("ix_checkout_quotes_guest_token_hash"),
        table_name="checkout_quotes",
    )
    op.drop_index(op.f("ix_checkout_quotes_customer_id"), table_name="checkout_quotes")
    op.drop_table("checkout_quotes")

    op.drop_index(op.f("ix_discounts_is_active"), table_name="discounts")
    op.drop_index(op.f("ix_discounts_listing_id"), table_name="discounts")
    op.drop_index(op.f("ix_discounts_code"), table_name="discounts")
    op.drop_table("discounts")

    op.drop_column("retailers", "state_source")
    op.drop_column("retailers", "state")
    op.drop_column("product_listings", "is_tax_verified")
    op.drop_column("product_listings", "tax_classification_source")
    op.drop_column("product_listings", "gst_rate_basis_points")
    op.drop_column("product_listings", "hsn_code")
