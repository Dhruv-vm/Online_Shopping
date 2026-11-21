"""retailer order status isolation: add fulfillment_status to order_items

Revision ID: 0015_order_item_fulfillment
Revises: 0014_admin_moderation_deals
Create Date: 2026-11-19 18:00:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0015_order_item_fulfillment"
down_revision: str | None = "0014_admin_moderation_deals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add fulfillment_status column with server default 'CONFIRMED'
    op.add_column(
        "order_items",
        sa.Column(
            "fulfillment_status",
            sa.String(32),
            server_default="CONFIRMED",
            nullable=False,
            index=True,
        ),
    )

    # 2. Backfill existing order items with their parent order's status
    op.execute(
        """
        UPDATE order_items
        SET fulfillment_status = orders.status
        FROM orders
        WHERE order_items.order_id = orders.id
        """
    )

    # 3. Add check constraint for valid fulfillment statuses
    op.create_check_constraint(
        "chk_order_item_fulfillment_status",
        "order_items",
        "fulfillment_status IN ('PENDING_PAYMENT', 'CONFIRMED', 'PROCESSING', 'PACKED', 'SHIPPED', 'OUT_FOR_DELIVERY', 'DELIVERED', 'CANCELLED', 'RETURNED')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "chk_order_item_fulfillment_status", "order_items", type_="check"
    )
    op.drop_column("order_items", "fulfillment_status")
