"use client";

import Link from "next/link";
import { Scale, Store } from "lucide-react";
import { ProductImage } from "@/components/catalogue/product-image";
import { useCompare } from "@/lib/compare/compare-context";
import { useI18n } from "@/lib/i18n/i18n-context";
import type { ProductSummary } from "@/types";

export function ProductCard({ product }: { product: ProductSummary }) {
  const { isInCompare, toggleCompare } = useCompare();
  const { t, money } = useI18n();
  const inCompare = isInCompare(product.slug);
  const discount =
    product.original_price_paise && product.original_price_paise > product.min_price_paise && product.min_price_paise > 0
      ? Math.round(((product.original_price_paise - product.min_price_paise) / product.original_price_paise) * 100)
      : 0;
  const available = product.is_in_stock && product.min_price_paise > 0;

  return (
    <article className="group relative flex h-full flex-col overflow-hidden rounded-xl border bg-white transition hover:-translate-y-0.5 hover:shadow-md">
      <Link href={`/products/${product.slug}`} className="flex h-full flex-col focus:outline-none focus-visible:ring-2 focus-visible:ring-brand">
        <div className="relative aspect-square overflow-hidden bg-surface">
          <ProductImage src={product.primary_image} alt={product.name} className="transition duration-300 group-hover:scale-105" />
          <div className="absolute left-2.5 top-2.5 flex flex-col items-start gap-1">
            {discount > 0 && available && (
              <span className="rounded-md bg-brand-yellow px-1.5 py-0.5 text-xs font-bold text-charcoal">{t("product.off", { n: discount })}</span>
            )}
            {!available && (
              <span className="rounded-md border border-red-200 bg-white/95 px-1.5 py-0.5 text-xs font-medium text-red-700">{t("common.outOfStock")}</span>
            )}
          </div>
        </div>
        <div className="flex flex-1 flex-col p-3.5">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{product.brand}</p>
          <h3 className="mt-0.5 line-clamp-2 text-sm font-semibold leading-snug text-charcoal group-hover:text-brand-dark">{product.name}</h3>
          <div className="mt-auto pt-3">
            {product.min_price_paise > 0 ? (
              <div className="flex items-baseline gap-2">
                <span className="text-base font-bold">{money(product.min_price_paise)}</span>
                {product.original_price_paise && product.original_price_paise > product.min_price_paise && (
                  <span className="text-xs text-muted-foreground line-through">{money(product.original_price_paise)}</span>
                )}
              </div>
            ) : (
              <span className="text-sm text-muted-foreground">{t("product.unavailable")}</span>
            )}
            <p className="mt-1 flex items-center gap-1 text-[11px] text-muted-foreground">
              <Store className="h-3 w-3 text-brand" />
              {t("product.sellers", { n: product.retailer_count })}
            </p>
          </div>
        </div>
      </Link>
      <button
        type="button"
        onClick={() => toggleCompare(product.slug)}
        aria-pressed={inCompare}
        className={`absolute right-2.5 top-2.5 flex items-center gap-1 rounded-full px-2 py-1 text-[11px] font-semibold shadow-sm backdrop-blur ${inCompare ? "bg-brand text-white" : "bg-white/90 text-charcoal"}`}
      >
        <Scale className="h-3 w-3" /> {inCompare ? t("product.comparing") : t("nav.compare")}
      </button>
    </article>
  );
}
