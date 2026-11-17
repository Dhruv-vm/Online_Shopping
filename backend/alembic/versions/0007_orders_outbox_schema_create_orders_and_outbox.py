"""create orders, order_items, order_status_history, outbox_events, idempotency_records

Revision ID: 0007_orders_outbox_schema
Revises: 0006_inventory_reservations
Create Date: 2026-11-17 22:45:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_orders_outbox_schema"
down_revision: str | None = "0006_inventory_reservations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create orders table
    op.create_table(
        "orders",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("order_number", sa.String(32), unique=True, nullable=False),
        sa.Column(
            "customer_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
            index=True,
        ),
        sa.Column("guest_token_hash", sa.String(64), nullable=True, index=True),
        sa.Column(
            "quote_id",
            sa.Uuid(),
            sa.ForeignKey("checkout_quotes.id", ondelete="RESTRICT"),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "reservation_id",
            sa.Uuid(),
            sa.ForeignKey("inventory_reservations.id", ondelete="RESTRICT"),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "delivery_address_snapshot",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=False,
        ),
        sa.Column("subtotal_paise", sa.BigInteger(), nullable=False),
        sa.Column(
            "discount_total_paise",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "delivery_fee_paise",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("cgst_paise", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("sgst_paise", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("igst_paise", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column(
            "total_tax_paise",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("total_payable_paise", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), server_default="INR", nullable=False),
        sa.Column(
            "status",
            sa.String(32),
            server_default="PENDING_PAYMENT",
            nullable=False,
            index=True,
        ),
        sa.Column(
            "payment_status",
            sa.String(32),
            server_default="NOT_INITIATED",
            nullable=False,
            index=True,
        ),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column(
            "payment_window_expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(customer_id IS NOT NULL AND guest_token_hash IS NULL) OR "
            "(customer_id IS NULL AND guest_token_hash IS NOT NULL)",
            name="chk_order_ownership",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING_PAYMENT', 'CONFIRMED', 'CANCELLED', 'SHIPPED', 'DELIVERED')",
            name="chk_order_status",
        ),
        sa.CheckConstraint(
            "payment_status IN ('NOT_INITIATED', 'PENDING', 'SUCCEEDED', 'FAILED', 'REQUIRES_RECONCILIATION', 'REFUNDED')",
            name="chk_order_payment_status",
        ),
        sa.CheckConstraint("subtotal_paise >= 0", name="chk_order_subtotal_paise"),
        sa.CheckConstraint(
            "total_payable_paise >= 0", name="chk_order_total_payable_paise"
        ),
    )

    # 2. Create order_items table
    op.create_table(
        "order_items",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "order_id",
            sa.Uuid(),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "listing_id",
            sa.Uuid(),
            sa.ForeignKey("product_listings.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "variant_id",
            sa.Uuid(),
            sa.ForeignKey("product_variants.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "retailer_id",
            sa.Uuid(),
            sa.ForeignKey("retailers.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("product_title", sa.String(255), nullable=False),
        sa.Column("variant_title", sa.String(255), nullable=False),
        sa.Column("sku", sa.String(100), nullable=True),
        sa.Column("hsn_code", sa.String(16), nullable=False),
        sa.Column("gst_rate_basis_points", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_original_price_paise", sa.BigInteger(), nullable=False),
        sa.Column("unit_selling_price_paise", sa.BigInteger(), nullable=False),
        sa.Column(
            "unit_discount_paise",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("unit_discounted_price_paise", sa.BigInteger(), nullable=False),
        sa.Column("total_selling_price_paise", sa.BigInteger(), nullable=False),
        sa.Column("taxable_base_paise", sa.BigInteger(), nullable=False),
        sa.Column("cgst_paise", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("sgst_paise", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("igst_paise", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column(
            "total_tax_paise",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("retailer_name", sa.String(255), nullable=False),
        sa.Column("retailer_state", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("quantity > 0", name="chk_order_item_quantity"),
        sa.CheckConstraint(
            "unit_selling_price_paise >= 0",
            name="chk_order_item_unit_selling_price_paise",
        ),
        sa.CheckConstraint(
            "total_selling_price_paise >= 0",
            name="chk_order_item_total_selling_price_paise",
        ),
    )

    # 3. Create order_status_history table
    op.create_table(
        "order_status_history",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "order_id",
            sa.Uuid(),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("from_status", sa.String(32), nullable=True),
        sa.Column("to_status", sa.String(32), nullable=False),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # 4. Create outbox_events table
    op.create_table(
        "outbox_events",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("aggregate_type", sa.String(64), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("schema_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(32),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING', 'PUBLISHED', 'FAILED')",
            name="chk_outbox_status",
        ),
    )
    op.create_index(
        "ix_outbox_pending",
        "outbox_events",
        ["created_at"],
        postgresql_where=sa.text("status = 'PENDING'"),
        sqlite_where=sa.text("status = 'PENDING'"),
    )
    op.create_index(
        "ix_outbox_aggregate",
        "outbox_events",
        ["aggregate_type", "aggregate_id"],
    )

    # 5. Create idempotency_records table
    op.create_table(
        "idempotency_records",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("scope", sa.String(64), nullable=False),
        sa.Column(
            "customer_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("guest_token_hash", sa.String(64), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column(
            "order_id",
            sa.Uuid(),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(customer_id IS NOT NULL AND guest_token_hash IS NULL) OR "
            "(customer_id IS NULL AND guest_token_hash IS NOT NULL)",
            name="chk_idempotency_ownership",
        ),
    )
    op.create_index(
        "uq_idempotency_customer",
        "idempotency_records",
        ["scope", "customer_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("customer_id IS NOT NULL"),
        sqlite_where=sa.text("customer_id IS NOT NULL"),
    )
    op.create_index(
        "uq_idempotency_guest",
        "idempotency_records",
        ["scope", "guest_token_hash", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("guest_token_hash IS NOT NULL"),
        sqlite_where=sa.text("guest_token_hash IS NOT NULL"),
    )

    # 6. Alter inventory_reservations: add order_id and update status check constraint
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.add_column(
            "inventory_reservations",
            sa.Column(
                "order_id",
                sa.Uuid(),
                sa.ForeignKey("orders.id", ondelete="SET NULL"),
                nullable=True,
                index=True,
            ),
        )
        op.drop_constraint(
            "chk_reservation_status",
            "inventory_reservations",
            type_="check",
        )
        op.create_check_constraint(
            "chk_reservation_status",
            "inventory_reservations",
            "status IN ('ACTIVE', 'ALLOCATED_TO_ORDER', 'CONFIRMED', 'RELEASED', 'EXPIRED')",
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_constraint(
            "chk_reservation_status",
            "inventory_reservations",
            type_="check",
        )
        # Cleanly transition any ALLOCATED_TO_ORDER rows before restoring the 0006 constraint
        op.execute(
            "UPDATE inventory_reservations SET status = 'RELEASED', release_reason = 'MIGRATION_DOWNGRADE' "
            "WHERE status = 'ALLOCATED_TO_ORDER'"
        )
        op.create_check_constraint(
            "chk_reservation_status",
            "inventory_reservations",
            "status IN ('ACTIVE', 'CONFIRMED', 'RELEASED', 'EXPIRED')",
        )
        op.drop_column("inventory_reservations", "order_id")

    op.drop_table("idempotency_records")
    op.drop_table("outbox_events")
    op.drop_table("order_status_history")
    op.drop_table("order_items")
    op.drop_table("orders")
