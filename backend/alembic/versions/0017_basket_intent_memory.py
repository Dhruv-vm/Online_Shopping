"""Phase 2C: Basket Intent Memory schema

Revision ID: 0017_basket_intent_memory
Revises: 0016_basket_mission
Create Date: 2026-11-20 11:00:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0017_basket_intent_memory"
down_revision: str | None = "0016_basket_mission"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    jsonb_type = postgresql.JSONB(astext_type=sa.Text()).with_variant(
        sa.JSON(), "sqlite"
    )

    # 1. Create customer_preference_profiles table
    op.create_table(
        "customer_preference_profiles",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "customer_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column("preferred_brands", jsonb_type, nullable=False, server_default="[]"),
        sa.Column(
            "preferred_categories", jsonb_type, nullable=False, server_default="[]"
        ),
        sa.Column(
            "preferred_retailers", jsonb_type, nullable=False, server_default="[]"
        ),
        sa.Column(
            "preferred_price_range", jsonb_type, nullable=False, server_default="{}"
        ),
        sa.Column(
            "preferred_attributes", jsonb_type, nullable=False, server_default="{}"
        ),
        sa.Column(
            "shopping_priorities", jsonb_type, nullable=False, server_default="[]"
        ),
        sa.Column(
            "category_preferences", jsonb_type, nullable=False, server_default="{}"
        ),
        sa.Column(
            "personalization_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
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

    # 2. Create customer_recurring_intentions table
    op.create_table(
        "customer_recurring_intentions",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "customer_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("category_ids", jsonb_type, nullable=False, server_default="[]"),
        sa.Column(
            "frequency",
            sa.String(32),
            nullable=False,
            server_default="MONTHLY",
        ),
        sa.Column("budget_paise", sa.BigInteger(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("last_executed_at", sa.DateTime(timezone=True), nullable=True),
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

    # 3. Create customer_intent_memories table
    op.create_table(
        "customer_intent_memories",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "customer_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "memory_type",
            sa.String(64),
            nullable=False,
            server_default="PREFERENCE",
        ),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("value", jsonb_type, nullable=False, server_default="{}"),
        sa.Column("summary", sa.String(255), nullable=False),
        sa.Column(
            "source",
            sa.String(32),
            nullable=False,
            server_default="CUSTOMER_STATED",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
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


def downgrade() -> None:
    op.drop_table("customer_intent_memories")
    op.drop_table("customer_recurring_intentions")
    op.drop_table("customer_preference_profiles")
