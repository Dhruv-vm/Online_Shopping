"use client";

import { ShoppingBasket } from "lucide-react";
import { useI18n } from "@/lib/i18n/i18n-context";

/** BASKET loading animation (respects prefers-reduced-motion). */
export function BasketLoader({ label, className = "" }: { label?: string; className?: string }) {
  const { t } = useI18n();
  const text = label ?? t("common.loading");
  return (
    <div role="status" aria-live="polite" className={`flex flex-col items-center justify-center gap-3 py-10 ${className}`}>
      <div className="relative h-12 w-12">
        <span className="basket-loader-dot absolute left-1/2 top-0 h-2 w-2 -translate-x-1/2 rounded-full bg-brand-yellow" />
        <span className="basket-loader-mark absolute inset-x-0 bottom-0 mx-auto flex h-10 w-10 items-center justify-center rounded-lg bg-brand text-white shadow">
          <ShoppingBasket className="h-5 w-5" aria-hidden />
        </span>
      </div>
      <span className="text-sm text-muted-foreground">{text}</span>
    </div>
  );
}
