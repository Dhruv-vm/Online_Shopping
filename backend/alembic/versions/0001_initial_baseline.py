"""initial baseline

Revision ID: 0001_initial_baseline
Revises:
Create Date: 2026-11-16 12:00:00.000000 UTC

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0001_initial_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Baseline migration marker for Phase 0 foundation
    pass


def downgrade() -> None:
    pass
