import asyncio
import logging

from sqlalchemy import delete, select, update

from app.core.config import settings
from app.core.database import get_session_factory
from app.core.logging import setup_logging
from app.core.search.client import get_opensearch_client
from app.core.search.index import (
    DEFAULT_SEARCH_ALIAS,
    IndexManager,
    get_write_alias_name,
)
from app.modules.cart.models import CartItem
from app.modules.catalogue.models import (
    Category,
    Product,
    ProductImage,
    ProductListing,
    ProductVariant,
    Retailer,
    RetailerVerificationDocument,
    RetailerVerificationHistory,
    StoreInventory,
)
from app.modules.inventory.models import InventoryReservation, InventoryReservationItem
from app.modules.orders.models import Order, OrderItem
from app.modules.pricing.models import CheckoutQuote, CheckoutQuoteItem, Discount
from app.seeds.seed_phase1_demo import (
    DEMO_PRODUCTS,
    TOP_LEVEL_CATEGORIES,
    seed_phase1_demo,
)

setup_logging()
logger = logging.getLogger("cleanup_marketplace_data")

APPROVED_CATEGORY_SLUGS = {c["slug"] for c in TOP_LEVEL_CATEGORIES}
APPROVED_PRODUCT_SLUGS = {p["slug"] for p in DEMO_PRODUCTS}
APPROVED_RETAILER_SLUGS = {"basket-mart", "basket-lifestyle"}


async def cleanup_database() -> dict[str, int]:
    """
    Idempotent, safe database cleanup preserving all financial ledger facts & transaction history:
    1. Preserves all orders, payments, captures, refunds, and customer accounts.
    2. Remaps legacy order items, quote items, and reservation items referencing obsolete test
       retailers/listings/variants to approved demo entities.
    3. Cleans up disposable cart items, unlinked quotes, unlinked reservations, and obsolete discounts.
    4. Deletes test products, variants, listings, inventory, and images.
    5. Deletes test categories (Admin Test Electronics, Analytics Cat, etc.).
    6. Deletes test retailers (Test Store, Analytics Test Store, etc.).
    7. Re-seeds exactly 50 initial demo products across exactly 2 approved retailers.
    8. Fully re-indexes canonical documents in OpenSearch and removes obsolete documents.
    """
    stats = {}
    session_factory = get_session_factory()

    # Ensure demo seed exists first so approved entities and listings are guaranteed available
    logger.info("Ensuring approved demo dataset is seeded...")
    await seed_phase1_demo()

    async with session_factory() as session:
        logger.info("=== STEP 1: RESOLVE APPROVED RETAILERS & ANCHOR LISTING ===")
        rets_res = await session.execute(
            select(Retailer).where(Retailer.slug.in_(APPROVED_RETAILER_SLUGS))
        )
        approved_retailers = {r.slug: r for r in rets_res.scalars().all()}
        bm_ret = approved_retailers.get("basket-mart")
        bl_ret = approved_retailers.get("basket-lifestyle")
        if not bm_ret or not bl_ret:
            raise RuntimeError(
                "Approved retailers 'basket-mart' and 'basket-lifestyle' must exist."
            )

        approved_ret_ids = [bm_ret.id, bl_ret.id]

        mart_anchor = (
            await session.execute(
                select(ProductListing.id, ProductListing.variant_id)
                .where(
                    ProductListing.retailer_id == bm_ret.id,
                    ProductListing.is_active.is_(True),
                )
                .limit(1)
            )
        ).first()

        if not mart_anchor:
            raise RuntimeError(
                "Approved retailer listing must exist to anchor historical items."
            )

        first_mart_listing = mart_anchor[0]
        first_mart_variant = mart_anchor[1]

        # Approved subquery expressions
        appr_p_stmt = select(Product.id).where(Product.slug.in_(APPROVED_PRODUCT_SLUGS))
        appr_v_stmt = select(ProductVariant.id).where(
            ProductVariant.product_id.in_(appr_p_stmt)
        )
        appr_l_stmt = select(ProductListing.id).where(
            ProductListing.variant_id.in_(appr_v_stmt),
            ProductListing.retailer_id.in_(approved_ret_ids),
        )

        logger.info(
            "=== STEP 2: REMAP ORDER ITEMS TO PRESERVE FINANCIAL TRANSACTION HISTORY ==="
        )
        upd_ord = await session.execute(
            update(OrderItem)
            .where(
                (OrderItem.retailer_id.not_in(approved_ret_ids))
                | (OrderItem.listing_id.not_in(appr_l_stmt))
                | (OrderItem.variant_id.not_in(appr_v_stmt))
            )
            .values(
                retailer_id=bm_ret.id,
                listing_id=first_mart_listing,
                variant_id=first_mart_variant,
            )
        )
        logger.info(
            f"Remapped {upd_ord.rowcount} legacy order items to approved retailer and listing."
        )

        logger.info("=== STEP 3: REMAP OR CLEAN INVENTORY RESERVATIONS & ITEMS ===")
        upd_ri = await session.execute(
            update(InventoryReservationItem)
            .where(
                (InventoryReservationItem.retailer_id.not_in(approved_ret_ids))
                | (InventoryReservationItem.listing_id.not_in(appr_l_stmt))
                | (InventoryReservationItem.variant_id.not_in(appr_v_stmt))
            )
            .values(
                retailer_id=bm_ret.id,
                listing_id=first_mart_listing,
                variant_id=first_mart_variant,
            )
        )
        logger.info(f"Remapped {upd_ri.rowcount} legacy reservation items.")

        order_res_ids = select(Order.reservation_id).where(
            Order.reservation_id.is_not(None)
        )
        del_ri_unlinked = await session.execute(
            delete(InventoryReservationItem).where(
                InventoryReservationItem.reservation_id.not_in(order_res_ids)
            )
        )
        del_r_unlinked = await session.execute(
            delete(InventoryReservation).where(
                InventoryReservation.id.not_in(order_res_ids)
            )
        )
        logger.info(
            f"Deleted unlinked reservations ({del_r_unlinked.rowcount}) and items ({del_ri_unlinked.rowcount})."
        )

        logger.info("=== STEP 4: REMAP OR CLEAN CHECKOUT QUOTES & ITEMS ===")
        upd_qi = await session.execute(
            update(CheckoutQuoteItem)
            .where(
                (CheckoutQuoteItem.retailer_id.not_in(approved_ret_ids))
                | (CheckoutQuoteItem.listing_id.not_in(appr_l_stmt))
                | (CheckoutQuoteItem.variant_id.not_in(appr_v_stmt))
            )
            .values(
                retailer_id=bm_ret.id,
                listing_id=first_mart_listing,
                variant_id=first_mart_variant,
            )
        )
        logger.info(f"Remapped {upd_qi.rowcount} legacy checkout quote items.")

        order_quote_ids = select(Order.quote_id).where(Order.quote_id.is_not(None))
        del_qi_unlinked = await session.execute(
            delete(CheckoutQuoteItem).where(
                CheckoutQuoteItem.quote_id.not_in(order_quote_ids)
            )
        )
        del_q_unlinked = await session.execute(
            delete(CheckoutQuote).where(CheckoutQuote.id.not_in(order_quote_ids))
        )
        logger.info(
            f"Deleted unlinked checkout quotes ({del_q_unlinked.rowcount}) and items ({del_qi_unlinked.rowcount})."
        )

        logger.info("=== STEP 5: CLEAN DISPOSABLE CART ITEMS ===")
        del_cart = await session.execute(
            delete(CartItem).where(
                (CartItem.listing_id.not_in(appr_l_stmt))
                | (CartItem.variant_id.not_in(appr_v_stmt))
                | (CartItem.retailer_id.not_in(approved_ret_ids))
            )
        )
        logger.info(f"Cleared {del_cart.rowcount} stale cart items.")

        logger.info("=== STEP 6: CLEAN DISCOUNTS / DEALS ===")
        del_disc = await session.execute(
            delete(Discount).where(
                (
                    Discount.product_id.is_not(None)
                    & Discount.product_id.not_in(appr_p_stmt)
                )
                | (
                    Discount.category_id.is_not(None)
                    & Discount.category_id.not_in(
                        select(Category.id).where(
                            Category.slug.in_(APPROVED_CATEGORY_SLUGS)
                        )
                    )
                )
                | (
                    Discount.listing_id.is_not(None)
                    & Discount.listing_id.not_in(appr_l_stmt)
                )
            )
        )
        logger.info(f"Deleted {del_disc.rowcount} obsolete discounts.")

        logger.info(
            "=== STEP 7: REMOVE TEST LISTINGS, INVENTORY, VARIANTS & PRODUCTS ==="
        )
        del_inv = await session.execute(
            delete(StoreInventory).where(StoreInventory.listing_id.not_in(appr_l_stmt))
        )
        logger.info(f"Deleted {del_inv.rowcount} stale store inventory records.")

        del_list = await session.execute(
            delete(ProductListing).where(ProductListing.id.not_in(appr_l_stmt))
        )
        stats["deleted_test_listings"] = del_list.rowcount
        logger.info(f"Deleted {del_list.rowcount} test product listings.")

        await session.execute(
            delete(ProductImage).where(ProductImage.product_id.not_in(appr_p_stmt))
        )
        del_var = await session.execute(
            delete(ProductVariant).where(ProductVariant.product_id.not_in(appr_p_stmt))
        )
        logger.info(f"Deleted {del_var.rowcount} test product variants.")

        del_prod = await session.execute(
            delete(Product).where(Product.slug.not_in(APPROVED_PRODUCT_SLUGS))
        )
        stats["deleted_test_products"] = del_prod.rowcount
        logger.info(f"Deleted {del_prod.rowcount} test products.")

        logger.info("=== STEP 8: REMOVE TEST CATEGORIES ===")
        await session.execute(
            update(Category)
            .where(Category.slug.not_in(APPROVED_CATEGORY_SLUGS))
            .values(parent_id=None)
        )
        del_cats = await session.execute(
            delete(Category).where(Category.slug.not_in(APPROVED_CATEGORY_SLUGS))
        )
        stats["deleted_test_categories"] = del_cats.rowcount
        logger.info(f"Deleted {del_cats.rowcount} test categories.")

        logger.info("=== STEP 9: REMOVE TEST RETAILERS ===")
        test_r_stmt = select(Retailer.id).where(
            Retailer.slug.not_in(APPROVED_RETAILER_SLUGS)
        )

        await session.execute(
            delete(RetailerVerificationDocument).where(
                RetailerVerificationDocument.retailer_id.in_(test_r_stmt)
            )
        )
        await session.execute(
            delete(RetailerVerificationHistory).where(
                RetailerVerificationHistory.retailer_id.in_(test_r_stmt)
            )
        )

        del_rets = await session.execute(
            delete(Retailer).where(Retailer.slug.not_in(APPROVED_RETAILER_SLUGS))
        )
        stats["deleted_test_retailers"] = del_rets.rowcount
        logger.info(f"Deleted {del_rets.rowcount} test retailers.")

        await session.commit()
        logger.info("=== DATABASE CLEANUP TRANSACTION COMMITTED SUCCESSFULLY ===")

    # Step 10: Re-run seed_phase1_demo to ensure exact canonical state
    logger.info("=== STEP 10: RE-VERIFY CANONICAL 50 DEMO PRODUCTS & 2 RETAILERS ===")
    await seed_phase1_demo()

    # Step 11: OpenSearch Reconciliation
    logger.info("=== STEP 11: SYNCHRONIZE OPENSEARCH DOCUMENTS ===")
    os_client = get_opensearch_client(settings)
    if await os_client.ping():
        index_manager = IndexManager(os_client)
        await index_manager.ensure_index_and_aliases()
        async with session_factory() as session:
            try:
                res = await os_client.search(
                    DEFAULT_SEARCH_ALIAS, {"query": {"match_all": {}}, "size": 500}
                )
                hits = res.get("hits", {}).get("hits", [])
                prods_res = await session.execute(
                    select(Product.id).where(Product.slug.in_(APPROVED_PRODUCT_SLUGS))
                )
                valid_prod_ids = {str(pid) for pid in prods_res.scalars().all()}

                write_alias = get_write_alias_name(settings.OPENSEARCH_INDEX_PREFIX)
                for h in hits:
                    doc_id = h.get("_id")
                    if doc_id not in valid_prod_ids:
                        try:
                            await os_client.delete_document(
                                index=write_alias, doc_id=doc_id
                            )
                        except Exception:
                            pass
            except Exception as e:
                logger.warning(f"Could not purge stale OpenSearch documents: {e}")

            indexed_count = await index_manager.reconcile_from_database(session)
            stats["opensearch_indexed"] = indexed_count
            logger.info(f"Reconciled {indexed_count} products into OpenSearch.")

    return stats


if __name__ == "__main__":
    asyncio.run(cleanup_database())
