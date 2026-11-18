"""outbox lease schema: claimed_by, claim_expires_at, next_attempt_at, correlation_id

Revision ID: 0009_outbox_lease
Revises: 0008_payments_razorpay_schema
Create Date: 2026-11-18 20:00:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009_outbox_lease"
down_revision: str | None = "0008_payments_razorpay_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add version column to orders table for aggregate root versioning
    op.add_column(
        "orders",
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
    )

    # 2. Add new columns to outbox_events
    op.add_column(
        "outbox_events", sa.Column("claimed_by", sa.String(128), nullable=True)
    )
    op.add_column(
        "outbox_events",
        sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "outbox_events",
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.add_column(
        "outbox_events", sa.Column("correlation_id", sa.String(128), nullable=True)
    )
    op.add_column(
        "outbox_events", sa.Column("aggregate_version", sa.Integer(), nullable=True)
    )

    # 3. Update status check constraint to include PROCESSING
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE outbox_events DROP CONSTRAINT IF EXISTS chk_outbox_status;"
        )
        op.execute(
            """
            ALTER TABLE outbox_events ADD CONSTRAINT chk_outbox_status CHECK (
                status IN ('PENDING', 'PROCESSING', 'PUBLISHED', 'FAILED')
            );
            """
        )

        # 4. Backfill aggregate_version for existing historical outbox events
        op.execute(
            """
            UPDATE outbox_events
            SET aggregate_version = (payload->>'aggregate_version')::INTEGER
            WHERE aggregate_version IS NULL AND payload ? 'aggregate_version';
            """
        )
        op.execute(
            """
            UPDATE outbox_events oe
            SET aggregate_version = sub.row_num
            FROM (
                SELECT id, ROW_NUMBER() OVER (PARTITION BY aggregate_id ORDER BY created_at ASC) as row_num
                FROM outbox_events
            ) sub
            WHERE oe.id = sub.id AND oe.aggregate_version IS NULL;
            """
        )

    # 5. Create partial index for lease polling
    op.create_index(
        "ix_outbox_lease_poll",
        "outbox_events",
        ["status", "next_attempt_at", "claim_expires_at"],
        postgresql_where=sa.text("status IN ('PENDING', 'PROCESSING')"),
        sqlite_where=sa.text("status IN ('PENDING', 'PROCESSING')"),
    )


def downgrade() -> None:
    # 1. Drop partial index
    op.drop_index("ix_outbox_lease_poll", table_name="outbox_events")

    # 2. Reset any PROCESSING rows to PENDING before restoring old constraint
    op.execute(
        "UPDATE outbox_events SET status = 'PENDING' WHERE status = 'PROCESSING';"
    )

    # 3. Restore old status check constraint
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE outbox_events DROP CONSTRAINT IF EXISTS chk_outbox_status;"
        )
        op.execute(
            """
            ALTER TABLE outbox_events ADD CONSTRAINT chk_outbox_status CHECK (
                status IN ('PENDING', 'PUBLISHED', 'FAILED')
            );
            """
        )

    # 4. Drop columns from outbox_events
    op.drop_column("outbox_events", "aggregate_version")
    op.drop_column("outbox_events", "correlation_id")
    op.drop_column("outbox_events", "next_attempt_at")
    op.drop_column("outbox_events", "claim_expires_at")
    op.drop_column("outbox_events", "claimed_by")

    # 5. Drop version column from orders
    op.drop_column("orders", "version")
