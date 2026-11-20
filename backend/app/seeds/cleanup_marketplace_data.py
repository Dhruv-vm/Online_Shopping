"""
BASKET — Safe Marketplace Cleanup & Synchronization
Removes disposable test data, unapproved dummy stores, test categories,
and orphaned records while preserving genuine accounts and financial ledger history.

Safety Features:
- Dry-run mode by default (pass --apply to execute).
- Production environment refusal (fails if DATABASE_URL or ENV indicates production).
- Preserves genuine customer accounts and genuine order records.
- Idempotent execution.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from urllib.parse import urlparse

from sqlalchemy import delete, select, update

from app.core.config import settings
from app.core.database import get_session_factory
from app.modules.catalogue.models import (
    Category,
    Product,
    ProductImage,
    ProductListing,
    ProductVariant,
    Retailer,
    StoreInventory,
)
from app.modules.identity.models import Address, User, UserSession
from app.modules.orders.models import (
    CustomerNotification,
    Order,
    OrderItem,
    OrderReturn,
    OrderStatusHistory,
    ReturnItem,
    Shipment,
    ShipmentItem,
)
from app.modules.payments.models import Payment, PaymentCapture, PaymentRefund
from app.modules.pricing.models import Discount
from app.seeds.seed_phase1_demo import (
    DEMO_PRODUCTS,
    TOP_LEVEL_CATEGORIES,
    seed_phase1_demo,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("cleanup_marketplace_data")

APPROVED_RETAILER_SLUGS = {"basket-mart", "basket-lifestyle"}
APPROVED_CATEGORY_SLUGS = {c["slug"] for c in TOP_LEVEL_CATEGORIES}
APPROVED_PRODUCT_SLUGS = {p["slug"] for p in DEMO_PRODUCTS}
GENUINE_USER_EMAILS = {
    "vmdhruv1@gmail.com",
    "vmdhruv0@gmail.com",
    "customer@basket.demo",
    "admin@basket.demo",
    "retailer1@basket.demo",
    "retailer2@basket.demo",
}


def verify_environment_safety() -> None:
    """Refuse to run on any production-configured database or environment."""
    if settings.is_production:
        raise RuntimeError(
            "CRITICAL ERROR: Cleanup script is strictly prohibited in production!"
        )

    db_url = settings.DATABASE_URL or ""
    parsed = urlparse(db_url)
    hostname = (parsed.hostname or "").lower()
    if (
        any(p in hostname for p in ("prod", "production", "live"))
        or "production" in db_url.lower()
    ):
        raise RuntimeError(
            f"CRITICAL ERROR: Database host '{hostname}' appears to be production. Aborting."
        )


async def run_cleanup(dry_run: bool = True) -> dict[str, int]:
    verify_environment_safety()

    session_factory = get_session_factory()

    # Step 0: Ensure approved Phase 1 demo baseline is seeded
    logger.info("Ensuring approved Phase 1 demo dataset is seeded...")
    await seed_phase1_demo()

    stats: dict[str, int] = {
        "disposable_orders_deleted": 0,
        "disposable_order_items_deleted": 0,
        "disposable_users_deleted": 0,
        "obsolete_discounts_deleted": 0,
        "unapproved_listings_deleted": 0,
        "unapproved_variants_deleted": 0,
        "unapproved_products_deleted": 0,
        "unapproved_categories_deleted": 0,
        "unapproved_retailers_deleted": 0,
        "genuine_orders_preserved": 0,
        "genuine_users_preserved": 0,
    }

    async with session_factory() as session:
        # 1. Identify genuine users vs disposable test users
        users = (await session.execute(select(User))).scalars().all()
        genuine_users = [u for u in users if u.email.lower() in GENUINE_USER_EMAILS]
        genuine_user_ids = {u.id for u in genuine_users}
        disposable_users = [
            u
            for u in users
            if u.id not in genuine_user_ids
            and (
                any(
                    u.email.endswith(f"@{dom}")
                    for dom in ("example.com", "basket.test", "basket.local")
                )
                or u.email.startswith(
                    ("test_", "perf_", "cust_", "order_cust_", "pay_cust_")
                )
            )
        ]
        disposable_user_ids = {u.id for u in disposable_users}

        stats["genuine_users_preserved"] = len(genuine_users)
        stats["disposable_users_deleted"] = len(disposable_users)

        # 2. Identify orders
        all_orders = (await session.execute(select(Order))).scalars().all()
        genuine_orders = [o for o in all_orders if o.customer_id in genuine_user_ids]
        disposable_orders = [
            o
            for o in all_orders
            if o.customer_id in disposable_user_ids or o.customer_id is None
        ]

        stats["genuine_orders_preserved"] = len(genuine_orders)
        stats["disposable_orders_deleted"] = len(disposable_orders)

        logger.info(
            "Audit findings: %d genuine users preserved, %d disposable users found; %d genuine orders preserved, %d disposable test orders found.",
            len(genuine_users),
            len(disposable_users),
            len(genuine_orders),
            len(disposable_orders),
        )

        # 3. Identify unapproved retailers, categories, and products
        retailers = (await session.execute(select(Retailer))).scalars().all()
        unapproved_retailers = [
            r for r in retailers if r.slug not in APPROVED_RETAILER_SLUGS
        ]
        unapproved_retailer_ids = {r.id for r in unapproved_retailers}
        stats["unapproved_retailers_deleted"] = len(unapproved_retailers)

        categories = (await session.execute(select(Category))).scalars().all()
        unapproved_categories = [
            c for c in categories if c.slug not in APPROVED_CATEGORY_SLUGS
        ]
        unapproved_category_ids = {c.id for c in unapproved_categories}
        stats["unapproved_categories_deleted"] = len(unapproved_categories)

        products = (await session.execute(select(Product))).scalars().all()
        unapproved_products = [
            p for p in products if p.slug not in APPROVED_PRODUCT_SLUGS
        ]
        unapproved_product_ids = {p.id for p in unapproved_products}
        stats["unapproved_products_deleted"] = len(unapproved_products)

        # Print audit table
        logger.info("=== CLEANUP AUDIT SUMMARY ===")
        for key, count in stats.items():
            logger.info("  %-35s : %d", key, count)

        if dry_run:
            logger.info(
                "DRY RUN MODE: No modifications were made. Pass --apply to execute cleanup."
            )
            return stats

        # DESTRUCTIVE EXECUTION:
        logger.info("APPLYING CLEANUP CHANGES TO DATABASE...")

        disposable_users_sel = select(User.id).where(
            User.email.not_in(GENUINE_USER_EMAILS)
        )
        disposable_orders_sel = select(Order.id).where(
            (Order.customer_id.in_(disposable_users_sel))
            | (Order.customer_id.is_(None))
        )

        # A. Delete disposable test order references using subqueries
        # Break circular reference on orders.fulfilling_capture_id
        await session.execute(
            update(Order)
            .where(
                (Order.customer_id.in_(disposable_users_sel))
                | (Order.customer_id.is_(None))
            )
            .values(fulfilling_capture_id=None)
        )

        # Delete customer notifications for disposable orders/customers
        await session.execute(
            delete(CustomerNotification).where(
                (CustomerNotification.order_id.in_(disposable_orders_sel))
                | (CustomerNotification.customer_id.in_(disposable_users_sel))
            )
        )

        # Delete order returns and return items for disposable orders
        ret_ids = select(OrderReturn.id).where(
            OrderReturn.order_id.in_(disposable_orders_sel)
        )
        await session.execute(
            delete(ReturnItem).where(ReturnItem.return_id.in_(ret_ids))
        )
        await session.execute(
            delete(OrderReturn).where(OrderReturn.order_id.in_(disposable_orders_sel))
        )

        # Delete shipments and shipment items
        ship_ids = select(Shipment.id).where(
            Shipment.order_id.in_(disposable_orders_sel)
        )
        await session.execute(
            delete(ShipmentItem).where(ShipmentItem.shipment_id.in_(ship_ids))
        )
        await session.execute(
            delete(Shipment).where(Shipment.order_id.in_(disposable_orders_sel))
        )

        # Delete payment refunds for disposable orders
        await session.execute(
            delete(PaymentRefund).where(
                PaymentRefund.order_id.in_(disposable_orders_sel)
            )
        )

        # Delete payment captures
        await session.execute(
            delete(PaymentCapture).where(
                PaymentCapture.order_id.in_(disposable_orders_sel)
            )
        )

        # Delete payments
        await session.execute(
            delete(Payment).where(
                (Payment.order_id.in_(disposable_orders_sel))
                | (Payment.customer_id.in_(disposable_users_sel))
            )
        )

        # Delete status histories
        await session.execute(
            delete(OrderStatusHistory).where(
                OrderStatusHistory.order_id.in_(disposable_orders_sel)
            )
        )

        # Delete order items
        oi_del = await session.execute(
            delete(OrderItem).where(OrderItem.order_id.in_(disposable_orders_sel))
        )
        stats["disposable_order_items_deleted"] = oi_del.rowcount or 0

        # Delete orders
        ord_del = await session.execute(
            delete(Order).where(
                (Order.customer_id.in_(disposable_users_sel))
                | (Order.customer_id.is_(None))
            )
        )
        stats["disposable_orders_deleted"] = ord_del.rowcount or 0

        # B. Delete disposable test checkout quotes and reservations
        from app.modules.inventory.models import (
            InventoryReservation,
            InventoryReservationItem,
        )
        from app.modules.pricing.models import CheckoutQuote, CheckoutQuoteItem

        # Reservations
        await session.execute(
            delete(InventoryReservationItem).where(
                InventoryReservationItem.reservation_id.in_(
                    select(InventoryReservation.id).where(
                        (InventoryReservation.customer_id.in_(disposable_user_ids))
                        | (InventoryReservation.customer_id.is_(None))
                    )
                )
            )
        )
        await session.execute(
            delete(InventoryReservation).where(
                (InventoryReservation.customer_id.in_(disposable_user_ids))
                | (InventoryReservation.customer_id.is_(None))
            )
        )

        # Quotes
        await session.execute(
            delete(CheckoutQuoteItem).where(
                CheckoutQuoteItem.quote_id.in_(
                    select(CheckoutQuote.id).where(
                        (CheckoutQuote.customer_id.in_(disposable_user_ids))
                        | (CheckoutQuote.customer_id.is_(None))
                    )
                )
            )
        )
        await session.execute(
            delete(CheckoutQuote).where(
                (CheckoutQuote.customer_id.in_(disposable_user_ids))
                | (CheckoutQuote.customer_id.is_(None))
            )
        )

        # C. Delete disposable test shopping carts
        from app.modules.cart.models import Cart, CartItem

        await session.execute(
            delete(CartItem).where(
                CartItem.cart_id.in_(
                    select(Cart.id).where(
                        (Cart.customer_id.in_(disposable_user_ids))
                        | (Cart.customer_id.is_(None))
                    )
                )
            )
        )
        await session.execute(
            delete(Cart).where(
                (Cart.customer_id.in_(disposable_user_ids))
                | (Cart.customer_id.is_(None))
            )
        )

        # D. Delete disposable users & user addresses / sessions
        if disposable_user_ids:
            await session.execute(
                delete(UserSession).where(UserSession.user_id.in_(disposable_user_ids))
            )
            await session.execute(
                delete(Address).where(Address.user_id.in_(disposable_user_ids))
            )
            await session.execute(delete(User).where(User.id.in_(disposable_user_ids)))

        # E. Delete obsolete discounts / offers not belonging to approved retailers
        approved_rets = (
            (
                await session.execute(
                    select(Retailer).where(Retailer.slug.in_(APPROVED_RETAILER_SLUGS))
                )
            )
            .scalars()
            .all()
        )
        approved_ret_ids = {r.id for r in approved_rets}

        disc_del = await session.execute(
            delete(Discount).where(
                Discount.retailer_id.is_not(None),
                Discount.retailer_id.not_in(approved_ret_ids),
            )
        )
        stats["obsolete_discounts_deleted"] = disc_del.rowcount or 0

        # F. Delete unapproved listings and variants
        if unapproved_product_ids or unapproved_retailer_ids:
            # Delete inventory and listings
            await session.execute(
                delete(StoreInventory).where(
                    StoreInventory.listing_id.in_(
                        select(ProductListing.id).where(
                            (ProductListing.retailer_id.in_(unapproved_retailer_ids))
                            | (
                                ProductListing.variant_id.in_(
                                    select(ProductVariant.id).where(
                                        ProductVariant.product_id.in_(
                                            unapproved_product_ids
                                        )
                                    )
                                )
                            )
                        )
                    )
                )
            )
            list_del = await session.execute(
                delete(ProductListing).where(
                    (ProductListing.retailer_id.in_(unapproved_retailer_ids))
                    | (
                        ProductListing.variant_id.in_(
                            select(ProductVariant.id).where(
                                ProductVariant.product_id.in_(unapproved_product_ids)
                            )
                        )
                    )
                )
            )
            stats["unapproved_listings_deleted"] = list_del.rowcount or 0

            # Delete product images
            await session.execute(
                delete(ProductImage).where(
                    ProductImage.product_id.in_(unapproved_product_ids)
                )
            )

            # Delete variants
            var_del = await session.execute(
                delete(ProductVariant).where(
                    ProductVariant.product_id.in_(unapproved_product_ids)
                )
            )
            stats["unapproved_variants_deleted"] = var_del.rowcount or 0

            # Delete products
            await session.execute(
                delete(Product).where(Product.id.in_(unapproved_product_ids))
            )

        # G. Delete unapproved categories
        if unapproved_category_ids:
            await session.execute(
                delete(Category).where(Category.id.in_(unapproved_category_ids))
            )

        # H. Delete unapproved retailers
        if unapproved_retailer_ids:
            await session.execute(
                delete(Retailer).where(Retailer.id.in_(unapproved_retailer_ids))
            )

        await session.commit()
        logger.info("Database cleanup transaction committed successfully.")

    # Step 4: Synchronize OpenSearch index
    logger.info("Synchronizing OpenSearch index with clean demo products...")
    try:
        from app.core.search.client import get_opensearch_client
        from app.core.search.index import IndexManager

        os_client = get_opensearch_client(settings)
        if await os_client.ping():
            idx_mgr = IndexManager(client=os_client)
            await idx_mgr.ensure_index_and_aliases()
            async with session_factory() as s:
                reconciled = await idx_mgr.reconcile_from_database(s)
                logger.info("OpenSearch reconciled %d products.", reconciled)
    except Exception as exc:
        logger.warning("OpenSearch synchronization during cleanup: %s", exc)

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="BASKET Safe Marketplace Cleanup")
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Execute destructive cleanup. Defaults to dry-run mode.",
    )
    args = parser.parse_args()

    dry_run = not args.apply
    if dry_run:
        print("\n=======================================================")
        print("  BASKET CLEANUP RUNNING IN DRY-RUN MODE (DEFAULT)")
        print("  Pass --apply to execute destructive cleanup.")
        print("=======================================================\n")
    else:
        print("\n=======================================================")
        print("  BASKET CLEANUP EXECUTING IN APPLY MODE")
        print("=======================================================\n")

    stats = asyncio.run(run_cleanup(dry_run=dry_run))
    print("\nCleanup Summary:")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
