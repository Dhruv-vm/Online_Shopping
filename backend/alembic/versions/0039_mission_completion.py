"""Backend-verified Basket Mission completion (final cycle, Part 10).

Additive columns on ``shopping_missions``:
* ``carted_at`` — when the mission's selected items were last sent to the cart.
* ``completed_at`` / ``completed_order_id`` — set once, by the payment-capture
  path, when a paid order contains every selected item of the mission.

Revision ID: 0039_mission_completion
Revises: 0038_recurring_baskets
Create Date: 2026-11-21 17:30:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0039_mission_completion"
down_revision: str | None = "0038_recurring_baskets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "shopping_missions",
        sa.Column("carted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "shopping_missions",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "shopping_missions",
        sa.Column(
            "completed_order_id",
            sa.Uuid(),
            sa.ForeignKey("orders.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_shopping_missions_completed_order_id",
        "shopping_missions",
        ["completed_order_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_shopping_missions_completed_order_id", table_name="shopping_missions"
    )
    op.drop_column("shopping_missions", "completed_order_id")
    op.drop_column("shopping_missions", "completed_at")
    op.drop_column("shopping_missions", "carted_at")
