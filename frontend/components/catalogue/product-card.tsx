"use client";

import { useRef } from "react";
import Link from "next/link";
import { Check, Heart, Loader2, Plus, Scale, Store } from "lucide-react";
import { ProductImage } from "@/components/catalogue/product-image";
import { useAuth } from "@/lib/auth/auth-context";
import { canShop } from "@/lib/auth/roles";
import { flyToCart, useQuickAdd } from "@/lib/cart/quick-add";
import { useCompare } from "@/lib/compare/compare-context";
import { useI18n } from "@/lib/i18n/i18n-context";
import { useWishlist } from "@/lib/wishlist/wishlist-context";
import type { ProductSummary } from "@/types";

/** Heart toggle for the device wishlist (outline → filled with a small pop). */
export function WishlistHeart({ slug, name, className = "" }: { slug: string; name: string; className?: string }) {
  const { t } = useI18n();
  const { has, toggle } = useWishlist();
  const saved = has(slug);
  return (
    <button
      type="button"
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        toggle(slug);
      }}
      aria-pressed={saved}
      aria-label={`${saved ? t("wishlist.remove") : t("wishlist.add")}: ${name}`}
      title={saved ? t("wishlist.remove") : t("wishlist.add")}
      className={`press flex h-9 w-9 items-center justify-center rounded-full bg-white/95 shadow-sm ring-1 ring-black/5 hover:bg-white ${className}`}
    >
      <Heart
        key={saved ? "on" : "off"}
        className={`h-[18px] w-[18px] transition-colors duration-base ${saved ? "animate-heart-pop fill-red-500 text-red-500" : "text-ink"}`}
      />
    </button>
  );
}

export function ProductCard({ product, eager = false }: { product: ProductSummary; eager?: boolean }) {
  const { isInCompare, toggleCompare } = useCompare();
  const { user } = useAuth();
  const { t, money } = useI18n();
  const media = useRef<HTMLDivElement>(null);
  const { state, message, add } = useQuickAdd(product.slug);
  const inCompare = isInCompare(product.slug);
  const available = product.is_in_stock && product.min_price_paise > 0;
  const discount =
    available && product.original_price_paise && product.original_price_paise > product.min_price_paise
      ? Math.round(((product.original_price_paise - product.min_price_paise) / product.original_price_paise) * 100)
      : 0;
  const shopper = canShop(user?.role);

  return (
    <article className="group relative flex h-full flex-col overflow-hidden rounded-card bg-white shadow-card ring-1 ring-black/[0.04] transition-[transform,box-shadow] duration-base ease-out hover:-translate-y-1 hover:shadow-card-hover">
      <Link href={`/products/${product.slug}`} className="flex h-full flex-col rounded-card focus:outline-none focus-visible:ring-2 focus-visible:ring-ink focus-visible:ring-offset-2">
        <div ref={media} className="relative aspect-square overflow-hidden bg-cream">
          <ProductImage
            src={product.primary_image}
            alt={product.name}
            eager={eager}
            className="transition-transform duration-slow ease-out group-hover:scale-[1.06]"
          />
          <div className="absolute left-3 top-3 flex flex-col items-start gap-1">
            {discount > 0 && (
              <span className="rounded-full bg-brand-yellow px-2 py-0.5 text-[11px] font-bold text-ink">{t("product.off", { n: discount })}</span>
            )}
            {!available && (
              <span className="rounded-full bg-white/95 px-2 py-0.5 text-[11px] font-semibold text-red-700 ring-1 ring-red-200">{t("common.outOfStock")}</span>
            )}
          </div>
        </div>
        <div className="flex flex-1 flex-col px-4 pb-4 pt-3">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{product.brand}</p>
          <h3 className="mt-1 line-clamp-2 min-h-[2.5rem] text-sm font-semibold leading-snug text-ink">{product.name}</h3>
          <div className="mt-auto flex items-end justify-between gap-2 pt-3">
            <div className="min-w-0">
              {product.min_price_paise > 0 ? (
                <div className="flex flex-wrap items-baseline gap-x-2">
                  <span className="text-lg font-extrabold tracking-tight text-ink">{money(product.min_price_paise)}</span>
                  {discount > 0 && <span className="text-xs text-muted-foreground line-through">{money(product.original_price_paise!)}</span>}
                </div>
              ) : (
                <span className="text-sm text-muted-foreground">{t("product.unavailable")}</span>
              )}
              <p className="mt-0.5 flex items-center gap-1 text-[11px] text-muted-foreground">
                <Store className="h-3 w-3" aria-hidden />
                {t("product.sellers", { n: product.retailer_count })}
              </p>
            </div>
            {/* spacer for the add button (rendered outside the link) */}
            {shopper && available && <span className="h-10 w-10 shrink-0" aria-hidden />}
          </div>
        </div>
      </Link>

      <div className="absolute right-3 top-3 flex flex-col items-end gap-2">
        <WishlistHeart slug={product.slug} name={product.name} />
        <button
          type="button"
          onClick={() => toggleCompare(product.slug)}
          aria-pressed={inCompare}
          title={inCompare ? t("product.comparing") : t("nav.compare")}
          aria-label={`${inCompare ? t("product.comparing") : t("nav.compare")}: ${product.name}`}
          className={`press flex h-9 w-9 items-center justify-center rounded-full shadow-sm ring-1 ring-black/5 transition-opacity duration-base sm:opacity-0 sm:group-hover:opacity-100 sm:focus-visible:opacity-100 ${inCompare ? "bg-ink text-white sm:opacity-100" : "bg-white/95 text-ink"}`}
        >
          <Scale className="h-4 w-4" />
        </button>
      </div>

      {shopper && available && (
        <button
          type="button"
          disabled={state === "adding"}
          onClick={async () => {
            if (await add()) flyToCart(media.current);
          }}
          aria-label={`${t("product.addToCart")}: ${product.name}`}
          title={state === "error" && message ? message : t("product.addToCart")}
          className={`press absolute bottom-4 right-4 flex h-10 w-10 items-center justify-center rounded-full shadow-sm ${
            state === "added" ? "bg-brand-green text-white" : state === "error" ? "bg-red-600 text-white" : "bg-brand-yellow text-ink hover:bg-brand-yellow-dark"
          }`}
        >
          {state === "adding" ? <Loader2 className="h-4 w-4 animate-spin" /> : state === "added" ? <Check className="h-5 w-5 animate-scale-in" /> : <Plus className="h-5 w-5" strokeWidth={2.5} />}
        </button>
      )}
      <span className="sr-only" aria-live="polite">
        {state === "added" ? t("product.added") : state === "error" ? message : ""}
      </span>
    </article>
  );
}
