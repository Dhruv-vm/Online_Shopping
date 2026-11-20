"""Phase 3H: Bharat Multilingual (content translations, user language)

Revision ID: 0025_bharat_multilingual
Revises: 0024_sale_stream
Create Date: 2026-11-20 22:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0025_bharat_multilingual"
down_revision: str | None = "0024_sale_stream"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "preferred_language", sa.String(8), server_default="en", nullable=False
        ),
    )
    op.create_table(
        "content_translations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("entity_type", sa.String(16), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("language", sa.String(8), nullable=False),
        sa.Column("field", sa.String(32), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column(
            "updated_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "entity_type",
            "entity_id",
            "language",
            "field",
            name="uq_content_translation",
        ),
    )
    op.create_index(
        "ix_content_translations_lookup",
        "content_translations",
        ["entity_type", "language", "entity_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_content_translations_lookup", table_name="content_translations")
    op.drop_table("content_translations")
    op.drop_column("users", "preferred_language")
