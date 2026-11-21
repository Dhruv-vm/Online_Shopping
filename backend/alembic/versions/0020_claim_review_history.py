"""Phase 2D: Passport claim review history and auditable revisions schema

Revision ID: 0020_passport_claim_review_history
Revises: 0019_product_passport
Create Date: 2026-11-20 18:10:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0020_claim_review_history"
down_revision: str | None = "0019_product_passport"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add version column to passport_claims
    op.add_column(
        "passport_claims",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )

    # 2. Create passport_claim_review_history table
    op.create_table(
        "passport_claim_review_history",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "claim_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("passport_claims.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("claim_scope", sa.String(32), nullable=False),
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
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("review_status", sa.String(32), nullable=False),
        sa.Column(
            "reviewer_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "review_status IN ('PENDING', 'VERIFIED', 'REJECTED')",
            name="chk_claim_review_history_status",
        ),
        sa.CheckConstraint(
            "action IN ('SUBMITTED', 'VERIFIED', 'REJECTED', 'REVISED')",
            name="chk_claim_review_history_action",
        ),
    )

    op.create_index(
        "ix_claim_review_history_claim_created",
        "passport_claim_review_history",
        ["claim_id", "created_at"],
    )

    # 3. Seed historical review entries for any pre-existing claims to guarantee complete data preservation
    op.execute(
        """
        INSERT INTO passport_claim_review_history (
            id, claim_id, claim_scope, claim_type, claim_key, claim_value,
            evidence_url, evidence_type, evidence_notes, is_public_evidence,
            action, review_status, reviewer_id, rejection_reason, created_at
        )
        SELECT
            gen_random_uuid(), id, claim_scope, claim_type, claim_key, claim_value,
            evidence_url, evidence_type, evidence_notes, is_public_evidence,
            CASE
                WHEN review_status = 'VERIFIED' THEN 'VERIFIED'
                WHEN review_status = 'REJECTED' THEN 'REJECTED'
                ELSE 'SUBMITTED'
            END,
            review_status, reviewed_by_user_id, rejection_reason, created_at
        FROM passport_claims
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_claim_review_history_claim_created",
        table_name="passport_claim_review_history",
    )
    op.drop_table("passport_claim_review_history")
    op.drop_column("passport_claims", "version")
