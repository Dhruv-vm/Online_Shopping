"""Admin audit log.

Revision ID: 0032_admin_audit_log
Revises: 0031_marketplace_completion
Create Date: 2026-11-21 00:10:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0032_admin_audit_log"
down_revision: str | None = "0031_marketplace_completion"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admin_audit_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "actor_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actor_email", sa.String(255), nullable=True),
        sa.Column("method", sa.String(8), nullable=False),
        sa.Column("route", sa.String(255), nullable=False),
        sa.Column("path", sa.String(512), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_admin_audit_created", "admin_audit_logs", ["created_at"])
    op.create_index(
        "ix_admin_audit_actor", "admin_audit_logs", ["actor_user_id", "created_at"]
    )
    op.create_index("ix_admin_audit_entity", "admin_audit_logs", ["entity_id"])


def downgrade() -> None:
    op.drop_index("ix_admin_audit_entity", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_actor", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_created", table_name="admin_audit_logs")
    op.drop_table("admin_audit_logs")
