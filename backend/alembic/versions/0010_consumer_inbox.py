"""consumer inbox and order summary projection schema

Revision ID: 0010_consumer_inbox
Revises: 0009_outbox_lease
Create Date: 2026-11-18 21:00:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010_consumer_inbox"
down_revision: str | None = "0009_outbox_lease"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create consumer_inbox table
    op.create_table(
        "consumer_inbox",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("consumer_group", sa.String(128), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("schema_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("aggregate_type", sa.String(64), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column("aggregate_version", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.String(32),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.String(1000), nullable=True),
        sa.Column("correlation_id", sa.String(128), nullable=True),
        sa.Column("dlq_published_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "consumer_group", "event_id", name="uq_consumer_inbox_group_event"
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'SUCCEEDED', 'FAILED', 'DEAD_LETTER')",
            name="chk_consumer_inbox_status",
        ),
    )

    op.create_index(
        "ix_consumer_inbox_group_event",
        "consumer_inbox",
        ["consumer_group", "event_id"],
    )
    op.create_index(
        "ix_consumer_inbox_aggregate",
        "consumer_inbox",
        ["aggregate_type", "aggregate_id", "aggregate_version"],
    )
    op.create_index(
        "ix_consumer_inbox_retention",
        "consumer_inbox",
        ["status", "processed_at"],
    )
    op.create_index(
        "ix_consumer_inbox_retry",
        "consumer_inbox",
        ["consumer_group", "status", "next_attempt_at"],
    )

    # 2. Create order_summary_projections table
    op.create_table(
        "order_summary_projections",
        sa.Column("order_id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("order_number", sa.String(64), unique=True, nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column(
            "payment_status",
            sa.String(32),
            server_default="NOT_INITIATED",
            nullable=False,
        ),
        sa.Column("total_payable_paise", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), server_default="INR", nullable=False),
        sa.Column("item_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_event_type", sa.String(128), nullable=False),
        sa.Column(
            "last_aggregate_version",
            sa.Integer(),
            server_default="1",
            nullable=False,
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
            nullable=False,
        ),
    )

    op.create_index(
        "ix_order_projections_status",
        "order_summary_projections",
        ["status"],
    )
    op.create_index(
        "ix_order_projections_customer",
        "order_summary_projections",
        ["customer_id"],
    )


def downgrade() -> None:
    # 1. Drop order_summary_projections table and indexes
    op.drop_index(
        "ix_order_projections_customer",
        table_name="order_summary_projections",
        if_exists=True,
    )
    op.drop_index(
        "ix_order_projections_status",
        table_name="order_summary_projections",
        if_exists=True,
    )
    op.drop_table("order_summary_projections")

    # 2. Drop consumer_inbox table and indexes
    op.drop_index(
        "ix_consumer_inbox_retry",
        table_name="consumer_inbox",
        if_exists=True,
    )
    op.drop_index(
        "ix_consumer_inbox_retention",
        table_name="consumer_inbox",
        if_exists=True,
    )
    op.drop_index(
        "ix_consumer_inbox_aggregate",
        table_name="consumer_inbox",
        if_exists=True,
    )
    op.drop_index(
        "ix_consumer_inbox_group_event",
        table_name="consumer_inbox",
        if_exists=True,
    )
    op.drop_table("consumer_inbox")
