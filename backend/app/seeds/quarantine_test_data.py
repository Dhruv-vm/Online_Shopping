"""BASKET — reversible quarantine of automated-test fixtures in a dev database.

Background: before the test suite was isolated (tests/conftest.py now always
uses a ``*_test`` database), plain ``pytest`` runs wrote thousands of fixture
rows into the development database: ``@example.com`` users, "Attacker Store
4a022f"-style retailers, "Apparel 1df3f444" categories and "Premium Organic
Coffee 422b4908" products. They polluted the storefront, retailer portal and
admin dashboards.

This script **hides** those fixtures instead of deleting them:

* Nothing is deleted. Orders, payments and history are never touched.
* Fixture users, retailers, categories, products, listings and offers are set
  inactive; each change is written to ``data_quarantine`` with the previous
  values, so ``--restore <batch>`` puts every row back exactly.
* Records belonging to the curated demo seed (``seed_phase1_demo``) or to any
  account that is not a test account are always kept.

Usage (from backend/):
    python -m app.seeds.quarantine_test_data            # dry run: report only
    python -m app.seeds.quarantine_test_data --apply    # quarantine
    python -m app.seeds.quarantine_test_data --list     # list batches
    python -m app.seeds.quarantine_test_data --restore <batch_id>
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import logging
from urllib.parse import urlparse

from sqlalchemy import text

from app.core.config import settings
from app.core.database import get_session_factory
from app.seeds.seed_phase1_demo import DEMO_PRODUCTS, TOP_LEVEL_CATEGORIES

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("quarantine_test_data")

TEST_EMAIL_PATTERNS = ("%@example.com", "%@basket.test", "%@basket.local")
APPROVED_RETAILER_SLUGS = ("basket-mart", "basket-lifestyle")

# entity_type -> (table, columns that are captured and restored)
ENTITIES: dict[str, tuple[str, tuple[str, ...]]] = {
    "user": ("users", ("is_active",)),
    "retailer": ("retailers", ("is_active", "is_open")),
    "listing": ("product_listings", ("is_active",)),
    "product": ("products", ("is_active",)),
    "category": ("categories", ("is_active",)),
    "discount": ("discounts", ("is_active",)),
}


def verify_environment_safety() -> None:
    if settings.is_production:
        raise RuntimeError("Refusing to run in a production environment.")
    url = settings.DATABASE_URL or ""
    host = (urlparse(url).hostname or "").lower()
    if any(p in host for p in ("prod", "production", "live")):
        raise RuntimeError(f"Database host '{host}' looks like production. Aborting.")


def _approved_category_slugs() -> list[str]:
    slugs = [c["slug"] for c in TOP_LEVEL_CATEGORIES]
    for c in TOP_LEVEL_CATEGORIES:
        slugs.extend(sc["slug"] for sc in c.get("children", []))
    return slugs


IDENTIFY_SQL = """
CREATE TEMP TABLE q_users ON COMMIT DROP AS
  SELECT id FROM users
  WHERE is_active AND (email ILIKE ANY(:test_patterns))
    AND email NOT ILIKE '%@basket.demo';

CREATE TEMP TABLE q_retailers ON COMMIT DROP AS
  SELECT r.id FROM retailers r
  WHERE (r.is_active OR r.is_open)
    AND r.slug <> ALL(:approved_retailers)
    AND (r.user_id IS NULL OR r.user_id IN (SELECT id FROM q_users));

CREATE TEMP TABLE kept_retailers ON COMMIT DROP AS
  SELECT id FROM retailers WHERE id NOT IN (SELECT id FROM q_retailers);

CREATE TEMP TABLE q_products ON COMMIT DROP AS
  SELECT p.id FROM products p
  WHERE p.is_active
    AND p.slug <> ALL(:approved_products)
    AND NOT EXISTS (
      SELECT 1 FROM product_variants v
      JOIN product_listings l ON l.variant_id = v.id
      WHERE v.product_id = p.id AND l.retailer_id IN (SELECT id FROM kept_retailers)
    );

CREATE TEMP TABLE q_listings ON COMMIT DROP AS
  SELECT l.id FROM product_listings l
  JOIN product_variants v ON v.id = l.variant_id
  WHERE l.is_active
    AND (l.retailer_id IN (SELECT id FROM q_retailers)
         OR v.product_id IN (SELECT id FROM q_products));

CREATE TEMP TABLE q_categories ON COMMIT DROP AS
  SELECT c.id FROM categories c
  WHERE c.is_active
    AND c.slug <> ALL(:approved_categories)
    AND NOT EXISTS (
      SELECT 1 FROM products p
      WHERE p.category_id = c.id AND p.is_active
        AND p.id NOT IN (SELECT id FROM q_products)
    )
    AND NOT EXISTS (
      SELECT 1 FROM categories ch
      JOIN products p ON p.category_id = ch.id
      WHERE ch.parent_id = c.id AND p.is_active
        AND p.id NOT IN (SELECT id FROM q_products)
    );

CREATE TEMP TABLE q_discounts ON COMMIT DROP AS
  SELECT d.id FROM discounts d
  WHERE d.is_active AND (
       d.name ILIKE '%test%'
    OR d.listing_id IN (SELECT id FROM q_listings)
    OR d.product_id IN (SELECT id FROM q_products)
    OR d.category_id IN (SELECT id FROM q_categories)
    OR d.scope IN (
         SELECT 'RET_' || left(replace(id::text, '-', ''), 24) FROM q_retailers)
  );
"""

ENTITY_TEMP = {
    "user": "q_users",
    "retailer": "q_retailers",
    "listing": "q_listings",
    "product": "q_products",
    "category": "q_categories",
    "discount": "q_discounts",
}

REASONS = {
    "user": "automated-test account (@example.com/@basket.test/@basket.local)",
    "retailer": "test fixture store not owned by a real account",
    "listing": "listing of a quarantined store or product",
    "product": "test fixture product not sold by any kept store",
    "category": "test fixture category with no kept products",
    "discount": "test offer or offer scoped to quarantined records",
}


async def run(apply: bool) -> dict[str, object]:
    verify_environment_safety()
    batch_id = "q-" + datetime.datetime.now(datetime.UTC).strftime("%Y%m%d%H%M%S%f")
    params = {
        "test_patterns": list(TEST_EMAIL_PATTERNS),
        "approved_retailers": list(APPROVED_RETAILER_SLUGS),
        "approved_products": [p["slug"] for p in DEMO_PRODUCTS],
        "approved_categories": _approved_category_slugs(),
    }
    counts: dict[str, object] = {"batch_id": None}
    async with get_session_factory()() as session:
        async with session.begin():
            for stmt in [s for s in IDENTIFY_SQL.split(";\n") if s.strip()]:
                await session.execute(text(stmt), params)
            for entity, temp in ENTITY_TEMP.items():
                counts[entity] = int(
                    (
                        await session.execute(text(f"SELECT count(*) FROM {temp}"))
                    ).scalar()
                    or 0
                )
            samples = {}
            for entity, (table, _) in ENTITIES.items():
                name_col = {"users": "email", "product_listings": "seller_sku"}.get(
                    table, "name"
                )
                rows = await session.execute(
                    text(
                        f"SELECT {name_col} FROM {table} WHERE id IN "
                        f"(SELECT id FROM {ENTITY_TEMP[entity]}) LIMIT 5"
                    )
                )
                samples[entity] = [r[0] for r in rows]
            logger.info(
                "Fixtures identified: %s",
                json.dumps({k: v for k, v in counts.items() if k != "batch_id"}),
            )
            for entity, names in samples.items():
                logger.info("  e.g. %s: %s", entity, names)
            if not apply:
                logger.info("Dry run only. Re-run with --apply to quarantine.")
                await session.rollback()
                return counts
            for entity, (table, cols) in ENTITIES.items():
                temp = ENTITY_TEMP[entity]
                state = ", ".join(f"'{c}', t.{c}" for c in cols)
                await session.execute(
                    text(
                        f"""
                        INSERT INTO data_quarantine
                          (id, batch_id, entity_type, entity_id, previous_state, reason)
                        SELECT gen_random_uuid(), :batch, :entity, t.id,
                               jsonb_build_object({state}), :reason
                        FROM {table} t WHERE t.id IN (SELECT id FROM {temp})
                        """
                    ),
                    {"batch": batch_id, "entity": entity, "reason": REASONS[entity]},
                )
                sets = ", ".join(f"{c} = false" for c in cols)
                await session.execute(
                    text(
                        f"UPDATE {table} SET {sets} WHERE id IN (SELECT id FROM {temp})"
                    )
                )
    logger.info(
        "Quarantine batch %s applied. Restore with --restore %s", batch_id, batch_id
    )
    counts["batch_id"] = batch_id
    return counts


async def restore(batch_id: str) -> int:
    verify_environment_safety()
    restored = 0
    async with get_session_factory()() as session:
        async with session.begin():
            for entity, (table, cols) in ENTITIES.items():
                sets = ", ".join(
                    f"{c} = (q.previous_state->>'{c}')::boolean" for c in cols
                )
                res = await session.execute(
                    text(
                        f"""
                        UPDATE {table} t SET {sets}
                        FROM data_quarantine q
                        WHERE q.batch_id = :batch AND q.entity_type = :entity
                          AND q.restored_at IS NULL AND q.entity_id = t.id
                        """
                    ),
                    {"batch": batch_id, "entity": entity},
                )
                restored += res.rowcount or 0
            await session.execute(
                text(
                    "UPDATE data_quarantine SET restored_at = now() "
                    "WHERE batch_id = :batch AND restored_at IS NULL"
                ),
                {"batch": batch_id},
            )
    logger.info("Restored %d records from batch %s", restored, batch_id)
    return restored


async def list_batches() -> None:
    async with get_session_factory()() as session:
        rows = await session.execute(
            text(
                "SELECT batch_id, entity_type, count(*), min(created_at), "
                "bool_and(restored_at IS NOT NULL) FROM data_quarantine "
                "GROUP BY 1, 2 ORDER BY 1, 2"
            )
        )
        for r in rows:
            logger.info("%s %-9s %6d created=%s restored=%s", *r)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--restore", metavar="BATCH_ID")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    if args.list:
        asyncio.run(list_batches())
    elif args.restore:
        asyncio.run(restore(args.restore))
    else:
        asyncio.run(run(apply=args.apply))


if __name__ == "__main__":
    main()
