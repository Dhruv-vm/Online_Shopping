"""multi-role portals: retailer profile extension, user association, and verification documents

Revision ID: 0012_multi_role_portals
Revises: 0011_order_postpurchase
Create Date: 2026-11-19 12:30:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012_multi_role_portals"
down_revision: str | None = "0011_order_postpurchase"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add tenant and store management columns to retailers
    op.add_column(
        "retailers",
        sa.Column("user_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_retailers_user_id_users",
        "retailers",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint("uq_retailers_user_id", "retailers", ["user_id"])
    op.create_index("ix_retailers_user_id", "retailers", ["user_id"])

    op.add_column(
        "retailers",
        sa.Column("business_address", sa.Text(), nullable=True),
    )
    op.add_column(
        "retailers",
        sa.Column("contact_phone", sa.String(15), nullable=True),
    )
    op.add_column(
        "retailers",
        sa.Column("contact_email", sa.String(255), nullable=True),
    )
    op.add_column(
        "retailers",
        sa.Column(
            "business_hours",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "retailers",
        sa.Column(
            "policies",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "retailers",
        sa.Column(
            "is_open",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )
    op.add_column(
        "retailers",
        sa.Column(
            "verification_status",
            sa.String(32),
            server_default=sa.text("'VERIFIED'"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_retailers_verification_status",
        "retailers",
        ["verification_status"],
    )

    # 2. Create retailer verification documents table
    op.create_table(
        "retailer_verification_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("retailer_id", sa.Uuid(), nullable=False),
        sa.Column("document_type", sa.String(32), nullable=False),
        sa.Column("document_url", sa.String(1024), nullable=False),
        sa.Column(
            "status",
            sa.String(32),
            server_default=sa.text("'PENDING'"),
            nullable=False,
        ),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
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
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_retailer_verification_documents"),
        sa.ForeignKeyConstraint(
            ["retailer_id"],
            ["retailers.id"],
            name="fk_retailer_docs_retailer_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_retailer_verification_documents_retailer_id",
        "retailer_verification_documents",
        ["retailer_id"],
    )
    op.create_index(
        "ix_retailer_verification_documents_status",
        "retailer_verification_documents",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_retailer_verification_documents_status",
        table_name="retailer_verification_documents",
    )
    op.drop_index(
        "ix_retailer_verification_documents_retailer_id",
        table_name="retailer_verification_documents",
    )
    op.drop_table("retailer_verification_documents")

    op.drop_index("ix_retailers_verification_status", table_name="retailers")
    op.drop_column("retailers", "verification_status")
    op.drop_column("retailers", "is_open")
    op.drop_column("retailers", "policies")
    op.drop_column("retailers", "business_hours")
    op.drop_column("retailers", "contact_email")
    op.drop_column("retailers", "contact_phone")
    op.drop_column("retailers", "business_address")
    op.drop_index("ix_retailers_user_id", table_name="retailers")
    op.drop_constraint("uq_retailers_user_id", "retailers", type_="unique")
    op.drop_constraint("fk_retailers_user_id_users", "retailers", type_="foreignkey")
    op.drop_column("retailers", "user_id")
