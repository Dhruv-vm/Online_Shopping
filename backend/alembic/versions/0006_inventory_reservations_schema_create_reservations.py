"""create inventory_reservations and inventory_reservation_items tables

Revision ID: 0006_inventory_reservations
Revises: 0005_pricing_quotes_schema
Create Date: 2026-11-17 17:35:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_inventory_reservations"
down_revision: str | None = "0005_pricing_quotes_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create inventory_reservations table
    op.create_table(
        "inventory_reservations",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("guest_token_hash", sa.String(length=64), nullable=True),
        sa.Column("quote_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'ACTIVE'"),
        ),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("release_reason", sa.String(length=255), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["users.id"],
            name="fk_inventory_reservations_customer_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["quote_id"],
            ["checkout_quotes.id"],
            name="fk_inventory_reservations_quote_id",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "(customer_id IS NOT NULL AND guest_token_hash IS NULL) OR "
            "(customer_id IS NULL AND guest_token_hash IS NOT NULL)",
            name="chk_reservation_ownership",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'CONFIRMED', 'RELEASED', 'EXPIRED')",
            name="chk_reservation_status",
        ),
    )

    op.create_index(
        op.f("ix_inventory_reservations_customer_id"),
        "inventory_reservations",
        ["customer_id"],
    )
    op.create_index(
        op.f("ix_inventory_reservations_guest_token_hash"),
        "inventory_reservations",
        ["guest_token_hash"],
    )
    op.create_index(
        op.f("ix_inventory_reservations_quote_id"),
        "inventory_reservations",
        ["quote_id"],
    )
    op.create_index(
        op.f("ix_inventory_reservations_status"),
        "inventory_reservations",
        ["status"],
    )
    op.create_index(
        op.f("ix_inventory_reservations_expires_at"),
        "inventory_reservations",
        ["expires_at"],
    )
    op.create_index(
        "ix_reservations_status_expires",
        "inventory_reservations",
        ["status", "expires_at"],
    )
    op.create_index(
        "uq_reservations_quote_active",
        "inventory_reservations",
        ["quote_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
        sqlite_where=sa.text("status = 'ACTIVE'"),
    )
    op.create_index(
        "uq_reservations_customer_idempotency",
        "inventory_reservations",
        ["customer_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text(
            "customer_id IS NOT NULL AND idempotency_key IS NOT NULL"
        ),
        sqlite_where=sa.text("customer_id IS NOT NULL AND idempotency_key IS NOT NULL"),
    )
    op.create_index(
        "uq_reservations_guest_idempotency",
        "inventory_reservations",
        ["guest_token_hash", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text(
            "guest_token_hash IS NOT NULL AND idempotency_key IS NOT NULL"
        ),
        sqlite_where=sa.text(
            "guest_token_hash IS NOT NULL AND idempotency_key IS NOT NULL"
        ),
    )

    # 2. Create inventory_reservation_items table
    op.create_table(
        "inventory_reservation_items",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("reservation_id", sa.Uuid(), nullable=False),
        sa.Column("listing_id", sa.Uuid(), nullable=False),
        sa.Column("retailer_id", sa.Uuid(), nullable=False),
        sa.Column("variant_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["reservation_id"],
            ["inventory_reservations.id"],
            name="fk_reservation_items_reservation_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["listing_id"],
            ["product_listings.id"],
            name="fk_reservation_items_listing_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["retailer_id"],
            ["retailers.id"],
            name="fk_reservation_items_retailer_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["product_variants.id"],
            name="fk_reservation_items_variant_id",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "quantity > 0", name="chk_reservation_item_quantity_positive"
        ),
        sa.UniqueConstraint(
            "reservation_id", "listing_id", name="uq_reservation_listing"
        ),
    )

    op.create_index(
        op.f("ix_inventory_reservation_items_reservation_id"),
        "inventory_reservation_items",
        ["reservation_id"],
    )
    op.create_index(
        op.f("ix_inventory_reservation_items_listing_id"),
        "inventory_reservation_items",
        ["listing_id"],
    )
    op.create_index(
        op.f("ix_inventory_reservation_items_retailer_id"),
        "inventory_reservation_items",
        ["retailer_id"],
    )
    op.create_index(
        op.f("ix_inventory_reservation_items_variant_id"),
        "inventory_reservation_items",
        ["variant_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_inventory_reservation_items_variant_id"),
        table_name="inventory_reservation_items",
    )
    op.drop_index(
        op.f("ix_inventory_reservation_items_retailer_id"),
        table_name="inventory_reservation_items",
    )
    op.drop_index(
        op.f("ix_inventory_reservation_items_listing_id"),
        table_name="inventory_reservation_items",
    )
    op.drop_index(
        op.f("ix_inventory_reservation_items_reservation_id"),
        table_name="inventory_reservation_items",
    )
    op.drop_table("inventory_reservation_items")

    op.drop_index(
        "uq_reservations_guest_idempotency", table_name="inventory_reservations"
    )
    op.drop_index(
        "uq_reservations_customer_idempotency", table_name="inventory_reservations"
    )
    op.drop_index("uq_reservations_quote_active", table_name="inventory_reservations")
    op.drop_index("ix_reservations_status_expires", table_name="inventory_reservations")
    op.drop_index(
        op.f("ix_inventory_reservations_expires_at"),
        table_name="inventory_reservations",
    )
    op.drop_index(
        op.f("ix_inventory_reservations_status"),
        table_name="inventory_reservations",
    )
    op.drop_index(
        op.f("ix_inventory_reservations_quote_id"),
        table_name="inventory_reservations",
    )
    op.drop_index(
        op.f("ix_inventory_reservations_guest_token_hash"),
        table_name="inventory_reservations",
    )
    op.drop_index(
        op.f("ix_inventory_reservations_customer_id"),
        table_name="inventory_reservations",
    )
    op.drop_table("inventory_reservations")
