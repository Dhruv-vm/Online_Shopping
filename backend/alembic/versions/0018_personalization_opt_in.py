"""Phase 2C: Make personalization opt-in default

Revision ID: 0018_personalization_opt_in
Revises: 0017_basket_intent_memory
Create Date: 2026-11-20 12:00:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0018_personalization_opt_in"
down_revision: str | None = "0017_basket_intent_memory"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "customer_preference_profiles",
        "personalization_enabled",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.false(),
    )


def downgrade() -> None:
    op.alter_column(
        "customer_preference_profiles",
        "personalization_enabled",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.true(),
    )
