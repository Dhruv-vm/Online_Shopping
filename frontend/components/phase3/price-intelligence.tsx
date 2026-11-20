"use client";

import { useEffect, useState } from "react";
import { getPriceIntelligence, type PriceIntelligence } from "@/lib/api/phase3";
import { useI18n } from "@/lib/i18n/i18n-context";
import { formatPrice } from "@/lib/utils";

const BADGE: Record<string, { key: string; cls: string }> = {
  GENUINE_DISCOUNT: { key: "feature.genuineDiscount", cls: "bg-emerald-100 text-emerald-800" },
  MRP_INFLATED: { key: "feature.mrpInflated", cls: "bg-amber-100 text-amber-800" },
};

/** Basket Price Intelligence widget (Phase 3F): lightweight SVG line chart. */
export function PriceIntelligencePanel({ listingId }: { listingId?: string | null }) {
  const { t } = useI18n();
  const [data, setData] = useState<PriceIntelligence | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (!listingId) return;
    setData(null);
    setFailed(false);
    getPriceIntelligence(listingId).then(setData).catch(() => setFailed(true));
  }, [listingId]);
  if (!listingId || failed || !data) return null;
  const pts = data.history.map((h) => h.price_paise);
  const w = 320, h = 80;
  const min = Math.min(...pts, data.current_price_paise), max = Math.max(...pts, data.current_price_paise);
  const path = pts
    .map((p, i) => `${i === 0 ? "M" : "L"}${(i / Math.max(1, pts.length - 1)) * w},${h - ((p - min) / Math.max(1, max - min)) * (h - 8) - 4}`)
    .join(" ");
  const badge = BADGE[data.badge];
  return (
    <section aria-label={t("feature.priceHistory")} className="rounded-lg border bg-white p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">{t("feature.priceHistory")} · {data.window_days}d</h3>
        {badge && <span className={`rounded px-2 py-0.5 text-xs font-semibold ${badge.cls}`}>{t(badge.key)}</span>}
      </div>
      {pts.length > 1 && (
        <svg viewBox={`0 0 ${w} ${h}`} className="mt-2 h-20 w-full" role="img" aria-label="Price trend">
          <path d={path} fill="none" stroke="currentColor" strokeWidth="2" className="text-emerald-600" />
        </svg>
      )}
      <dl className="mt-2 grid grid-cols-3 gap-2 text-xs">
        <div><dt className="text-gray-500">{t("feature.lowestPrice")}</dt><dd className="font-semibold">{formatPrice(data.lowest_price_paise)}</dd></div>
        <div><dt className="text-gray-500">Highest</dt><dd className="font-semibold">{formatPrice(data.highest_price_paise)}</dd></div>
        <div><dt className="text-gray-500">30-day avg</dt><dd className="font-semibold">{data.average_price_30d_paise ? formatPrice(data.average_price_30d_paise) : "—"}</dd></div>
      </dl>
      <p className="mt-2 text-xs text-gray-500">{data.badge_reason}</p>
    </section>
  );
}
