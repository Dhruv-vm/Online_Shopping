"""retailer inventory thresholds: add low_stock_threshold to store_inventory

Revision ID: 0013_retailer_inventory
Revises: 0012_multi_role_portals
Create Date: 2026-11-19 13:30:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0013_retailer_inventory"
down_revision: str | None = "0012_multi_role_portals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "store_inventory",
        sa.Column(
            "low_stock_threshold",
            sa.Integer(),
            server_default=sa.text("10"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("store_inventory", "low_stock_threshold")
