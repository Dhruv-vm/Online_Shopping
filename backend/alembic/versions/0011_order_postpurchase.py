"""order post-purchase lifecycle: shipments, tracking, cancellations, returns, notifications

Revision ID: 0011_order_postpurchase
Revises: 0010_consumer_inbox
Create Date: 2026-11-19 11:00:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011_order_postpurchase"
down_revision: str | None = "0010_consumer_inbox"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --------------------------------------------------------------------------
    # 1. Update orders table with post-purchase fields and expanded lifecycle status
    # --------------------------------------------------------------------------
    op.add_column(
        "orders",
        sa.Column("guest_access_token_hash", sa.String(64), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("cancellation_reason", sa.String(255), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_orders_guest_access_token_hash",
        "orders",
        ["guest_access_token_hash"],
        unique=False,
    )

    # Replace chk_order_status check constraint with expanded post-purchase lifecycle states
    op.drop_constraint("chk_order_status", "orders", type_="check")
    op.create_check_constraint(
        "chk_order_status",
        "orders",
        "status IN ('PENDING_PAYMENT', 'CONFIRMED', 'PROCESSING', 'PACKED', 'SHIPPED', 'OUT_FOR_DELIVERY', 'DELIVERED', 'CANCELLED', 'RETURNED')",
    )

    # --------------------------------------------------------------------------
    # 2. Create shipments table
    # --------------------------------------------------------------------------
    op.create_table(
        "shipments",
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
        ),
        sa.Column("shipment_number", sa.String(32), unique=True, nullable=False),
        sa.Column("carrier_name", sa.String(64), nullable=False),
        sa.Column("carrier_code", sa.String(32), nullable=False),
        sa.Column("tracking_number", sa.String(64), nullable=False),
        sa.Column("tracking_url", sa.String(512), nullable=True),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="LABEL_CREATED",
        ),
        sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("estimated_delivery_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column(
            "carrier_event_history",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
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
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('LABEL_CREATED', 'PICKED_UP', 'IN_TRANSIT', 'OUT_FOR_DELIVERY', 'DELIVERED', 'EXCEPTION', 'CANCELLED')",
            name="chk_shipment_status",
        ),
    )
    op.create_index("ix_shipments_order_id", "shipments", ["order_id"])
    op.create_index("ix_shipments_shipment_number", "shipments", ["shipment_number"])
    op.create_index("ix_shipments_tracking_number", "shipments", ["tracking_number"])
    op.create_index("ix_shipments_status", "shipments", ["status"])

    # --------------------------------------------------------------------------
    # 3. Create shipment_items table (partial shipments support)
    # --------------------------------------------------------------------------
    op.create_table(
        "shipment_items",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "shipment_id",
            sa.Uuid(),
            sa.ForeignKey("shipments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "order_item_id",
            sa.Uuid(),
            sa.ForeignKey("order_items.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("quantity > 0", name="chk_shipment_item_qty"),
    )
    op.create_index("ix_shipment_items_shipment_id", "shipment_items", ["shipment_id"])
    op.create_index(
        "ix_shipment_items_order_item_id", "shipment_items", ["order_item_id"]
    )

    # --------------------------------------------------------------------------
    # 4. Create order_returns table
    # --------------------------------------------------------------------------
    op.create_table(
        "order_returns",
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
        ),
        sa.Column("return_number", sa.String(32), unique=True, nullable=False),
        sa.Column(
            "customer_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("guest_token_hash", sa.String(64), nullable=True),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="REQUESTED",
        ),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("customer_notes", sa.Text(), nullable=True),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column(
            "refund_amount_paise",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "payment_refund_id",
            sa.Uuid(),
            sa.ForeignKey("payment_refunds.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("inspected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
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
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('REQUESTED', 'APPROVED', 'REJECTED', 'PICKUP_PENDING', 'RECEIVED', 'INSPECTED', 'REFUND_PENDING', 'REFUNDED', 'CANCELLED')",
            name="chk_return_status",
        ),
        sa.CheckConstraint("refund_amount_paise >= 0", name="chk_return_refund_amount"),
    )
    op.create_index("ix_order_returns_order_id", "order_returns", ["order_id"])
    op.create_index("ix_order_returns_customer_id", "order_returns", ["customer_id"])
    op.create_index(
        "ix_order_returns_guest_token_hash", "order_returns", ["guest_token_hash"]
    )
    op.create_index(
        "ix_order_returns_return_number", "order_returns", ["return_number"]
    )
    op.create_index("ix_order_returns_status", "order_returns", ["status"])
    op.create_index(
        "ix_order_returns_idempotency_key", "order_returns", ["idempotency_key"]
    )

    # --------------------------------------------------------------------------
    # 5. Create return_items table
    # --------------------------------------------------------------------------
    op.create_table(
        "return_items",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "return_id",
            sa.Uuid(),
            sa.ForeignKey("order_returns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "order_item_id",
            sa.Uuid(),
            sa.ForeignKey("order_items.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("refund_subtotal_paise", sa.BigInteger(), nullable=False),
        sa.Column("condition_grade", sa.String(32), nullable=True),
        sa.Column(
            "restock_approved", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("quantity > 0", name="chk_return_item_qty"),
        sa.CheckConstraint(
            "refund_subtotal_paise >= 0", name="chk_return_item_refund_subtotal"
        ),
    )
    op.create_index("ix_return_items_return_id", "return_items", ["return_id"])
    op.create_index("ix_return_items_order_item_id", "return_items", ["order_item_id"])

    # --------------------------------------------------------------------------
    # 6. Create return_status_history table
    # --------------------------------------------------------------------------
    op.create_table(
        "return_status_history",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "return_id",
            sa.Uuid(),
            sa.ForeignKey("order_returns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_status", sa.String(32), nullable=True),
        sa.Column("to_status", sa.String(32), nullable=False),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("actor", sa.String(64), server_default="CUSTOMER", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_return_status_history_return_id", "return_status_history", ["return_id"]
    )

    # --------------------------------------------------------------------------
    # 7. Create customer_notifications table
    # --------------------------------------------------------------------------
    op.create_table(
        "customer_notifications",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("guest_token_hash", sa.String(64), nullable=True),
        sa.Column(
            "order_id",
            sa.Uuid(),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("is_read", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_notifications_customer_id", "customer_notifications", ["customer_id"]
    )
    op.create_index(
        "ix_notifications_guest_token_hash",
        "customer_notifications",
        ["guest_token_hash"],
    )
    op.create_index("ix_notifications_is_read", "customer_notifications", ["is_read"])
    op.create_index(
        "ix_notifications_created_at", "customer_notifications", ["created_at"]
    )


def downgrade() -> None:
    op.drop_table("customer_notifications")
    op.drop_table("return_status_history")
    op.drop_table("return_items")
    op.drop_table("order_returns")
    op.drop_table("shipment_items")
    op.drop_table("shipments")

    op.drop_index("ix_orders_guest_access_token_hash", table_name="orders")
    op.drop_column("orders", "delivered_at")
    op.drop_column("orders", "cancelled_at")
    op.drop_column("orders", "cancellation_reason")
    op.drop_column("orders", "guest_access_token_hash")

    op.drop_constraint("chk_order_status", "orders", type_="check")
    op.create_check_constraint(
        "chk_order_status",
        "orders",
        "status IN ('PENDING_PAYMENT', 'CONFIRMED', 'CANCELLED', 'SHIPPED', 'DELIVERED')",
    )
