"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Heart } from "lucide-react";
import { ProductCard } from "@/components/catalogue/product-card";
import { apiClient } from "@/lib/api/client";
import { useI18n } from "@/lib/i18n/i18n-context";
import { useWishlist } from "@/lib/wishlist/wishlist-context";
import type { ProductDetail, ProductSummary } from "@/types";

function toSummary(p: ProductDetail): ProductSummary {
  const img = p.images?.find((i) => i.is_primary) ?? p.images?.[0];
  const stores = new Set(p.variants.flatMap((v) => v.listings.filter((l) => l.is_active).map((l) => l.retailer_id)));
  return {
    id: p.id,
    name: p.name,
    slug: p.slug,
    brand: p.brand,
    category_id: p.category_id,
    category_name: p.category_name,
    category_slug: p.category_slug,
    primary_image: img?.url ?? null,
    min_price_paise: p.min_price_paise,
    max_price_paise: p.max_price_paise,
    original_price_paise: p.original_price_paise ?? null,
    currency: p.currency,
    is_in_stock: p.is_in_stock,
    variant_count: p.variants.length,
    retailer_count: stores.size,
  };
}

export default function WishlistPage() {
  const { t } = useI18n();
  const { slugs, remove } = useWishlist();
  const [items, setItems] = useState<ProductSummary[] | null>(null);
  const [gone, setGone] = useState<string[]>([]);
  const key = slugs.join("|");

  useEffect(() => {
    let alive = true;
    if (!slugs.length) {
      setItems([]);
      return;
    }
    Promise.allSettled(slugs.map((s) => apiClient.getProduct(s))).then((res) => {
      if (!alive) return;
      const ok: ProductSummary[] = [];
      const missing: string[] = [];
      res.forEach((r, i) => (r.status === "fulfilled" ? ok.push(toSummary(r.value)) : missing.push(slugs[i])));
      setItems(ok);
      setGone(missing);
    });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return (
    <div className="container-page py-10">
      <div className="mb-8 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight">{t("wishlist.title")}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{t("wishlist.subtitle")}</p>
        </div>
      </div>
      {items === null ? (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          {Array.from({ length: Math.max(1, Math.min(slugs.length, 5)) }).map((_, i) => (
            <div key={i} className="aspect-[3/4] animate-pulse rounded-card bg-cream" />
          ))}
        </div>
      ) : items.length === 0 && gone.length === 0 ? (
        <div className="mx-auto max-w-md rounded-card bg-white p-10 text-center shadow-card">
          <Heart className="mx-auto h-10 w-10 text-ink/25" />
          <p className="mt-3 font-bold">{t("wishlist.empty")}</p>
          <p className="mt-1 text-sm text-muted-foreground">{t("wishlist.emptyBody")}</p>
          <Link href="/products" className="press mt-5 inline-flex h-11 items-center rounded-full bg-brand-yellow px-6 text-sm font-semibold text-ink hover:bg-brand-yellow-dark">
            {t("nav.catalogue")}
          </Link>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
            {items.map((p) => (
              <ProductCard key={p.slug} product={p} />
            ))}
          </div>
          {gone.length > 0 && (
            <div className="mt-6 rounded-xl bg-white p-4 text-sm shadow-card">
              <p className="font-semibold">{t("wishlist.removed")}</p>
              <ul className="mt-2 flex flex-wrap gap-2">
                {gone.map((s) => (
                  <li key={s}>
                    <button type="button" onClick={() => remove(s)} className="rounded-full bg-cream px-3 py-1 text-xs hover:bg-brand-light">
                      {s} ✕
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  );
}
