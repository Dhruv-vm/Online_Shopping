"""Secure WhatsApp invitations for community buying (final cycle, Part 9).

New table ``group_buy_invites``: one row per shared invitation, storing only a
SHA-256 hash of the token, its expiry, use count and optional revocation.

Revision ID: 0037_group_buy_invites
Revises: 0036_intent_workflow
Create Date: 2026-11-21 15:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0037_group_buy_invites"
down_revision: str | None = "0036_intent_workflow"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "group_buy_invites",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "campaign_id",
            sa.Uuid(),
            sa.ForeignKey("group_buy_campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("uses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("token_hash", name="uq_group_buy_invites_token_hash"),
    )
    op.create_index(
        "ix_group_buy_invites_campaign_id", "group_buy_invites", ["campaign_id"]
    )
    op.create_index(
        "ix_group_buy_invites_created_by_user_id",
        "group_buy_invites",
        ["created_by_user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_group_buy_invites_created_by_user_id", table_name="group_buy_invites"
    )
    op.drop_index("ix_group_buy_invites_campaign_id", table_name="group_buy_invites")
    op.drop_table("group_buy_invites")
