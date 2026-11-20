"""Phase 2D: Product Passport schema

Revision ID: 0019_product_passport
Revises: 0018_personalization_opt_in
Create Date: 2026-11-20 12:00:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0019_product_passport"
down_revision: str | None = "0018_personalization_opt_in"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    jsonb_type = postgresql.JSONB(astext_type=sa.Text()).with_variant(
        sa.JSON(), "sqlite"
    )

    # 1. Create product_passports table
    op.create_table(
        "product_passports",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "product_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column("manufacturer", sa.String(255), nullable=True),
        sa.Column("country_of_origin", sa.String(100), nullable=True),
        sa.Column("model_number", sa.String(100), nullable=True),
        sa.Column("gtin_ean_upc", sa.String(100), nullable=True),
        sa.Column("materials", jsonb_type, nullable=False, server_default="[]"),
        sa.Column("technical_specs", jsonb_type, nullable=False, server_default="{}"),
        sa.Column("package_contents", jsonb_type, nullable=False, server_default="[]"),
        sa.Column("usage_instructions", sa.Text(), nullable=True),
        sa.Column("safety_instructions", sa.Text(), nullable=True),
        sa.Column("warranty_info", sa.Text(), nullable=True),
        sa.Column("certifications", jsonb_type, nullable=False, server_default="[]"),
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

    # 2. Create listing_passports table
    op.create_table(
        "listing_passports",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "listing_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("product_listings.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column(
            "retailer_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("retailers.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "item_condition",
            sa.String(50),
            nullable=False,
            server_default="NEW",
        ),
        sa.Column("seller_warranty", sa.Text(), nullable=True),
        sa.Column("packaging_notes", sa.Text(), nullable=True),
        sa.Column("fulfillment_notes", sa.Text(), nullable=True),
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
        sa.CheckConstraint(
            "item_condition IN ('NEW', 'REFURBISHED', 'OPEN_BOX', 'PRE_OWNED')",
            name="chk_listing_passport_condition",
        ),
    )

    # 3. Create passport_claims table
    op.create_table(
        "passport_claims",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "passport_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("product_passports.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "listing_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("product_listings.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "retailer_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("retailers.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "claim_scope",
            sa.String(32),
            nullable=False,
            server_default="LISTING",
            index=True,
        ),
        sa.Column("claim_type", sa.String(64), nullable=False),
        sa.Column("claim_key", sa.String(128), nullable=False),
        sa.Column("claim_value", sa.Text(), nullable=False),
        sa.Column("evidence_url", sa.String(1024), nullable=True),
        sa.Column(
            "evidence_type",
            sa.String(64),
            nullable=False,
            server_default="DOCUMENT",
        ),
        sa.Column("evidence_notes", sa.Text(), nullable=True),
        sa.Column(
            "is_public_evidence",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "review_status",
            sa.String(32),
            nullable=False,
            server_default="PENDING",
            index=True,
        ),
        sa.Column(
            "submitted_by_user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "reviewed_by_user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
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
            nullable=False,
        ),
        sa.CheckConstraint(
            "review_status IN ('PENDING', 'VERIFIED', 'REJECTED')",
            name="chk_passport_claim_status",
        ),
        sa.CheckConstraint(
            "claim_scope IN ('PRODUCT', 'LISTING')",
            name="chk_passport_claim_scope",
        ),
    )

    op.create_index(
        "ix_passport_claims_status_scope",
        "passport_claims",
        ["review_status", "claim_scope"],
    )


def downgrade() -> None:
    op.drop_index("ix_passport_claims_status_scope", table_name="passport_claims")
    op.drop_table("passport_claims")
    op.drop_table("listing_passports")
    op.drop_table("product_passports")
