"""Simulated bids flag on basket_auction_bids.

Additive column on ``basket_auction_bids``:
* ``is_simulated`` — boolean flag indicating a simulated/demo quotation.

Revision ID: 0040_auction_simulated_bids
Revises: 0039_mission_completion
Create Date: 2026-11-22 01:30:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0040_auction_simulated_bids"
down_revision: str | None = "0039_mission_completion"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "basket_auction_bids",
        sa.Column(
            "is_simulated",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("basket_auction_bids", "is_simulated")
