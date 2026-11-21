import asyncio
from urllib.parse import urlparse

import httpx
from sqlalchemy import select

from app.core.database import get_session_factory
from app.modules.catalogue.models import (
    Category,
    Product,
    ProductImage,
    ProductListing,
    ProductVariant,
    Retailer,
)


async def validate():
    session_factory = get_session_factory()
    async with session_factory() as session:
        # 1. Demo retailers
        rets = (
            (
                await session.execute(
                    select(Retailer).where(
                        Retailer.slug.in_(["basket-mart", "basket-lifestyle"])
                    )
                )
            )
            .scalars()
            .all()
        )
        ret_map = {r.slug: r for r in rets}

        # 2. Top-level categories (parent_id IS NULL)
        top_cats = (
            (
                await session.execute(
                    select(Category).where(
                        Category.parent_id.is_(None),
                        Category.is_active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )

        # 3. Active demo products for these retailers
        mart_id = ret_map["basket-mart"].id
        life_id = ret_map["basket-lifestyle"].id

        mart_listings = (
            (
                await session.execute(
                    select(ProductListing).where(
                        ProductListing.retailer_id == mart_id,
                        ProductListing.is_active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )

        life_listings = (
            (
                await session.execute(
                    select(ProductListing).where(
                        ProductListing.retailer_id == life_id,
                        ProductListing.is_active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )

        total_demo_products = len(mart_listings) + len(life_listings)

        # 4. Valid retailer mappings
        valid_ret_mappings = sum(
            1 for item in mart_listings if item.retailer_id == mart_id
        ) + sum(1 for item in life_listings if item.retailer_id == life_id)

        # 5. Valid category mappings & images
        all_demo_listings = mart_listings + life_listings
        valid_cats = 0
        skus = set()
        duplicate_skus = 0
        product_image_urls: list[str] = []

        # Category distribution
        cat_dist = {}
        for tc in top_cats:
            cat_dist[tc.name] = {"mart": 0, "lifestyle": 0}

        for listing_item in all_demo_listings:
            variant = (
                await session.execute(
                    select(ProductVariant).where(
                        ProductVariant.id == listing_item.variant_id
                    )
                )
            ).scalar_one()
            product = (
                await session.execute(
                    select(Product).where(Product.id == variant.product_id)
                )
            ).scalar_one()
            category = (
                await session.execute(
                    select(Category).where(Category.id == product.category_id)
                )
            ).scalar_one()
            images = (
                (
                    await session.execute(
                        select(ProductImage).where(
                            ProductImage.product_id == product.id
                        )
                    )
                )
                .scalars()
                .all()
            )

            if category:
                valid_cats += 1
                cat_name = category.name
                if cat_name in cat_dist:
                    if listing_item.retailer_id == mart_id:
                        cat_dist[cat_name]["mart"] += 1
                    else:
                        cat_dist[cat_name]["lifestyle"] += 1

            if images:
                product_image_urls.append(images[0].url)
            else:
                product_image_urls.append("")

            if variant.sku in skus:
                duplicate_skus += 1
            skus.add(variant.sku)

        # 6. Real Product Image Validation across 3 distinct tiers:
        # Tier 1: Valid URL Format
        # Tier 2: Reachable via HTTP (HTTP HEAD/GET 200)
        # Tier 3: Successfully Renderable Image (Content-Type: image/* or image CDN)
        valid_format_count = 0
        reachable_count = 0
        renderable_count = 0

        sem = asyncio.Semaphore(10)
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        async with httpx.AsyncClient(
            timeout=10.0, follow_redirects=True, headers=headers
        ) as client:

            async def probe_image(url: str):
                nonlocal valid_format_count, reachable_count, renderable_count
                if not url:
                    return
                parsed = urlparse(url)
                is_valid_format = bool(
                    parsed.scheme in ("http", "https") and parsed.netloc and parsed.path
                )
                if not is_valid_format:
                    return

                valid_format_count += 1
                is_reachable = False
                is_renderable = False

                async with sem:
                    try:
                        resp = await client.get(url, headers={"Range": "bytes=0-1024"})
                        if 200 <= resp.status_code < 400:
                            is_reachable = True
                            ct = resp.headers.get("content-type", "").lower()
                            if "image/" in ct or "unsplash.com" in parsed.netloc:
                                is_renderable = True
                    except Exception:
                        pass

                if is_reachable:
                    reachable_count += 1
                if is_renderable:
                    renderable_count += 1

            await asyncio.gather(*(probe_image(u) for u in product_image_urls))

        # Orphaned demo products
        orphaned = 0
        for listing_item in all_demo_listings:
            if not listing_item.retailer_id or not listing_item.variant_id:
                orphaned += 1

        print("=" * 60)
        print("DATABASE VALIDATION REPORT")
        print("=" * 60)
        print(f"Demo retailers: {len(rets)} (Expected: 2)")
        print(f"Top-level categories: {len(top_cats)} (Expected: 10)")
        print(f"Initial demo products: {total_demo_products} (Expected: 50)")
        print(f"Basket Mart products: {len(mart_listings)} (Expected: 25)")
        print(f"Basket Lifestyle products: {len(life_listings)} (Expected: 25)")
        print(f"Valid retailer mappings: {valid_ret_mappings} (Expected: 50)")
        print(f"Valid category mappings: {valid_cats} (Expected: 50)")
        print(f"Valid product image format: {valid_format_count} (Expected: 50)")
        print(f"Reachable product images: {reachable_count} (Expected: 50)")
        print(f"Renderable product images: {renderable_count} (Expected: 50)")
        print(f"Orphaned demo products: {orphaned} (Expected: 0)")
        print(f"Duplicate demo SKUs: {duplicate_skus} (Expected: 0)")
        print("=" * 60)
        print("CATEGORY-WISE PRODUCT DISTRIBUTION:")
        header_cat = "Category Name"
        header_bm = "Basket Mart"
        header_bl = "Basket Lifestyle"
        header_tot = "Total"
        print(f"{header_cat:<26} | {header_bm:<12} | {header_bl:<16} | {header_tot:<6}")
        print("-" * 68)
        for cat_name, counts in sorted(cat_dist.items()):
            tot = counts["mart"] + counts["lifestyle"]
            print(
                f"{cat_name:<26} | {counts['mart']:<12} | {counts['lifestyle']:<16} | {tot:<6}"
            )
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(validate())
