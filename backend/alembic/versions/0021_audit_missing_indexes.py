"""Audit 2026-11: add indexes declared on the models but never migrated

`alembic check` reported two indexes present in the SQLAlchemy models that no
migration ever created:

* ix_inventory_reservations_idempotency_key — used by every reservation
  idempotency lookup (ReservationRepository.get_by_idempotency).
* ix_webhook_created — used by webhook reconciliation scans ordered by age.

Both are additive, created IF NOT EXISTS, and fully reversible. No data is
modified.

Revision ID: 0021_audit_missing_indexes
Revises: 0020_claim_review_history
Create Date: 2026-11-20 21:00:00.000000+00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0021_audit_missing_indexes"
down_revision: str | None = "0020_claim_review_history"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_inventory_reservations_idempotency_key",
        "inventory_reservations",
        ["idempotency_key"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_webhook_created",
        "webhook_events",
        ["created_at"],
        unique=False,
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_webhook_created", table_name="webhook_events", if_exists=True)
    op.drop_index(
        "ix_inventory_reservations_idempotency_key",
        table_name="inventory_reservations",
        if_exists=True,
    )
