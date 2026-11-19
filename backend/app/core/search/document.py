from __future__ import annotations

import datetime
from typing import Any


def build_product_document(
    product: Any,
    variants: list[Any] | None = None,
    category: Any | None = None,
    aggregate_version: int = 1,
) -> dict[str, Any]:
    """
    Deterministic projection from PostgreSQL entities to a canonical OpenSearch JSON document.
    Pure mathematical projection guaranteeing repeatable outputs across replays.
    """
    prod_id = str(product.id)
    now_iso = datetime.datetime.now(datetime.UTC).isoformat()

    # Category resolution
    cat = category or getattr(product, "category", None)
    category_id = (
        str(product.category_id)
        if product.category_id
        else (str(cat.id) if cat else "")
    )
    category_name = cat.name if cat else ""
    category_slug = cat.slug if cat else ""
    parent_cat_name = cat.parent.name if cat and getattr(cat, "parent", None) else None

    # Variants and listings extraction
    prod_variants = (
        variants if variants is not None else getattr(product, "variants", [])
    )
    variant_ids: list[str] = []
    retailer_ids: list[str] = []
    listing_ids: list[str] = []
    prices: list[int] = []
    original_prices: list[int] = []
    attributes_map: dict[str, list[str]] = {}
    retailer_entries: list[dict[str, Any]] = []
    variant_entries: list[dict[str, Any]] = []
    total_available_stock = 0
    any_in_stock = False
    ratings: list[float] = []

    for v in prod_variants:
        v_id = str(v.id)
        variant_ids.append(v_id)

        # Variant attributes aggregation
        v_attrs = getattr(v, "attributes", {}) or {}
        for k, val in v_attrs.items():
            k_clean = str(k).strip().lower()
            val_clean = str(val).strip()
            if k_clean not in attributes_map:
                attributes_map[k_clean] = []
            if val_clean not in attributes_map[k_clean]:
                attributes_map[k_clean].append(val_clean)

        v_listings = getattr(v, "listings", []) or []
        v_in_stock = False

        for lst in v_listings:
            if not getattr(lst, "is_active", True):
                continue

            ret = getattr(lst, "retailer", None)
            if ret is not None:
                ret_is_active = getattr(ret, "is_active", True)
                if ret_is_active is False:
                    continue
                ret_status = getattr(ret, "verification_status", "VERIFIED")
                if ret_status is not None and ret_status != "VERIFIED":
                    continue

            l_id = str(lst.id)
            listing_ids.append(l_id)
            ret_id = str(lst.retailer_id)
            if ret_id not in retailer_ids:
                retailer_ids.append(ret_id)

            prices.append(int(lst.selling_price_paise))
            original_prices.append(int(lst.original_price_paise))

            # Stock from store_inventory
            inv = getattr(lst, "inventory", None)
            avail = 0
            if inv is not None:
                avail = max(0, int(inv.on_hand_quantity) - int(inv.reserved_quantity))
            elif hasattr(lst, "available_quantity"):
                avail = max(0, int(lst.available_quantity))

            if avail > 0:
                v_in_stock = True
                any_in_stock = True
                total_available_stock += avail

            ret = getattr(lst, "retailer", None)
            ret_name = ret.name if ret else f"Retailer-{ret_id[:8]}"
            if ret and hasattr(ret, "rating"):
                ratings.append(float(ret.rating))

            retailer_entries.append(
                {
                    "retailer_id": ret_id,
                    "retailer_name": ret_name,
                    "listing_id": l_id,
                    "selling_price_paise": int(lst.selling_price_paise),
                    "original_price_paise": int(lst.original_price_paise),
                    "is_in_stock": avail > 0,
                    "available_quantity": avail,
                }
            )

        variant_entries.append(
            {
                "variant_id": v_id,
                "name": v.name,
                "sku": v.sku,
                "attributes": v_attrs,
                "is_in_stock": v_in_stock,
            }
        )

    # Images extraction
    primary_img: str | None = None
    images = getattr(product, "images", []) or []
    for img in sorted(
        images,
        key=lambda x: (
            not getattr(x, "is_primary", False),
            getattr(x, "sort_order", 0),
        ),
    ):
        primary_img = img.url
        break

    min_price = min(prices) if prices else 0
    max_price = max(prices) if prices else 0
    avg_rating = sum(ratings) / len(ratings) if ratings else 5.0

    # Build searchable text bag-of-words for universal indexing
    searchable_terms = [
        product.name,
        product.brand,
        category_name,
        product.description or "",
    ]
    for vals in attributes_map.values():
        searchable_terms.extend(vals)
    searchable_text = " ".join(t for t in searchable_terms if t).strip()

    return {
        "product_id": prod_id,
        "name": product.name,
        "slug": product.slug,
        "brand": product.brand,
        "description": product.description or "",
        "category_id": category_id,
        "category_name": category_name,
        "category_slug": category_slug,
        "parent_category_name": parent_cat_name,
        "primary_image_url": primary_img,
        "min_price_paise": min_price,
        "max_price_paise": max_price,
        "currency": "INR",
        "is_in_stock": any_in_stock,
        "total_available_quantity": total_available_stock,
        "rating": round(avg_rating, 1),
        "is_active": bool(getattr(product, "is_active", True)),
        "variant_ids": sorted(set(variant_ids)),
        "retailer_ids": sorted(set(retailer_ids)),
        "listing_ids": sorted(set(listing_ids)),
        "variants": variant_entries,
        "retailers": retailer_entries,
        "attributes": attributes_map,
        "searchable_text": searchable_text,
        "aggregate_version": int(aggregate_version),
        "indexed_at": now_iso,
    }
