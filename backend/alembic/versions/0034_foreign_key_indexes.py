"""Index foreign-key columns found unindexed by the migration verification.

scripts/verify-migrations.sh flagged eight FK columns with no full leading
index. Without one, deleting or updating the referenced row (for example a
product listing or a user) forces a sequential scan of the referencing table,
and the common lookups (a user's price alerts, a listing's group buys) cannot
use an index. Five were introduced by 0031; three predate it (0014, 0027).

Revision ID: 0034_foreign_key_indexes
Revises: 0033_retailer_onboarding_media
Create Date: 2026-11-21 07:30:00.000000+00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0034_foreign_key_indexes"
down_revision: str | None = "0033_retailer_onboarding_media"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (table, column) — index name follows SQLAlchemy's ix_<table>_<column>.
INDEXES = [
    ("group_buy_campaigns", "created_by_user_id"),
    ("group_buy_campaigns", "listing_id"),
    ("group_buy_campaigns", "template_id"),
    ("group_buy_templates", "listing_id"),
    ("group_buy_templates", "retailer_id"),
    ("price_alerts", "triggered_listing_id"),
    ("price_alerts", "user_id"),
    ("retailers", "reviewed_by_user_id"),
]


def upgrade() -> None:
    for table, column in INDEXES:
        op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade() -> None:
    for table, column in reversed(INDEXES):
        op.drop_index(f"ix_{table}_{column}", table_name=table)
