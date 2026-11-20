"""Retailer onboarding (GSTIN, document numbers) and listing images.

Revision ID: 0033_retailer_onboarding_media
Revises: 0032_admin_audit_log
Create Date: 2026-11-21 00:40:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0033_retailer_onboarding_media"
down_revision: str | None = "0032_admin_audit_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("retailers", sa.Column("gstin", sa.String(15), nullable=True))
    op.add_column(
        "retailer_verification_documents",
        sa.Column("document_number", sa.String(64), nullable=True),
    )
    op.add_column(
        "product_listings", sa.Column("image_url", sa.String(1024), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("product_listings", "image_url")
    op.drop_column("retailer_verification_documents", "document_number")
    op.drop_column("retailers", "gstin")
