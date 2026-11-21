from __future__ import annotations

from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.core.database import Base


def test_migration_chain_is_linear_and_single_head():
    """Verify Alembic migration topology is strictly linear with exactly one head."""
    alembic_ini = Path(__file__).resolve().parent.parent / "alembic.ini"
    cfg = Config(str(alembic_ini))
    script = ScriptDirectory.from_config(cfg)

    # Exactly one migration head
    heads = script.get_heads()
    assert len(heads) == 1, f"Expected exactly 1 migration head, found {heads}"
    assert heads[0] == "0034_foreign_key_indexes"

    # Walk from head to base verifying linear unbroken parent links
    current = script.get_revision(heads[0])
    visited = []
    while current is not None:
        visited.append(current.revision)
        down = current.down_revision
        if down is None:
            break
        assert isinstance(down, str), (
            f"Branching/multiple down_revisions detected at {current.revision}: {down}"
        )
        current = script.get_revision(down)

    expected_revisions = [
        "0034_foreign_key_indexes",
        "0033_retailer_onboarding_media",
        "0032_admin_audit_log",
        "0031_marketplace_completion",
        "0030_dukaan_vs_dukaan",
        "0029_ai_negotiator",
        "0028_community_exchange",
        "0027_community_buying",
        "0026_demand_gap",
        "0025_bharat_multilingual",
        "0024_sale_stream",
        "0023_price_intelligence",
        "0022_marketplace_foundation",
        "0021_audit_missing_indexes",
        "0020_claim_review_history",
        "0019_product_passport",
        "0018_personalization_opt_in",
        "0017_basket_intent_memory",
        "0016_basket_mission",
        "0015_order_item_fulfillment",
        "0014_admin_moderation_deals",
        "0013_retailer_inventory",
        "0012_multi_role_portals",
        "0011_order_postpurchase",
        "0010_consumer_inbox",
        "0009_outbox_lease",
        "0008_payments_razorpay_schema",
        "0007_orders_outbox_schema",
        "0006_inventory_reservations",
        "0005_pricing_quotes_schema",
        "0004_cart_schema",
        "0003_identity_schema",
        "0002_catalogue_schema",
        "0001_initial_baseline",
    ]
    assert visited == expected_revisions


def test_migration_metadata_includes_all_models():
    """Verify Base.metadata has registered shopping_missions, intent memories, passport, and all domain tables."""
    import app.modules.intent.models  # noqa: F401
    import app.modules.missions.models  # noqa: F401
    import app.modules.passport.models  # noqa: F401

    table_names = Base.metadata.tables.keys()
    assert "customer_preference_profiles" in table_names
    assert "customer_recurring_intentions" in table_names
    assert "customer_intent_memories" in table_names
    assert "shopping_missions" in table_names
    assert "shopping_mission_items" in table_names
    assert "product_passports" in table_names
    assert "listing_passports" in table_names
    assert "passport_claims" in table_names
    assert "passport_claim_review_history" in table_names
    assert "product_listings" in table_names
    assert "orders" in table_names
    assert "order_items" in table_names
    assert "payments" in table_names
    assert "inventory_reservations" in table_names


@pytest.mark.asyncio
async def test_database_schema_constraints_and_indices():
    """Verify database schema has applied all checks, foreign keys, and indexes for Basket Mission."""
    from app.core.database import get_session_factory

    session_factory = get_session_factory()
    assert session_factory is not None

    async with session_factory() as db_session:
        # 1. Verify shopping_missions table exists with expected columns
        cols_query = await db_session.execute(
            text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'shopping_missions'
            """)
        )
        cols = {r[0]: (r[1], r[2]) for r in cols_query.fetchall()}
        assert "id" in cols
        assert "customer_id" in cols
        assert "title" in cols
        assert "budget_paise" in cols
        assert "status" in cols
        assert "people_count" in cols
        assert "preferences" in cols
        assert "excluded_brands" in cols

        # 2. Verify shopping_mission_items columns
        item_cols_query = await db_session.execute(
            text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'shopping_mission_items'
            """)
        )
        item_cols = {r[0]: (r[1], r[2]) for r in item_cols_query.fetchall()}
        assert "id" in item_cols
        assert "mission_id" in item_cols
        assert "product_id" in item_cols
        assert "variant_id" in item_cols
        assert "listing_id" in item_cols
        assert "retailer_id" in item_cols
        assert "quantity" in item_cols
        assert "unit_price_paise" in item_cols
        assert "is_selected" in item_cols
        assert "group_name" in item_cols

        # 3. Verify check constraints in PostgreSQL
        chk_query = await db_session.execute(
            text("""
                SELECT conname
                FROM pg_constraint
                WHERE conname IN (
                    'chk_shopping_mission_budget_positive',
                    'chk_shopping_mission_people_positive',
                    'chk_shopping_mission_status',
                    'chk_mission_item_quantity_positive',
                    'chk_mission_item_unit_price_nonnegative',
                    'chk_listing_passport_condition',
                    'chk_passport_claim_status',
                    'chk_passport_claim_scope',
                    'chk_claim_review_history_status',
                    'chk_claim_review_history_action'
                )
            """)
        )
        constraints = {r[0] for r in chk_query.fetchall()}
        assert "chk_shopping_mission_budget_positive" in constraints
        assert "chk_shopping_mission_people_positive" in constraints
        assert "chk_shopping_mission_status" in constraints
        assert "chk_mission_item_quantity_positive" in constraints
        assert "chk_mission_item_unit_price_nonnegative" in constraints
        assert "chk_listing_passport_condition" in constraints
        assert "chk_passport_claim_status" in constraints
        assert "chk_passport_claim_scope" in constraints
        assert "chk_claim_review_history_status" in constraints
        assert "chk_claim_review_history_action" in constraints
