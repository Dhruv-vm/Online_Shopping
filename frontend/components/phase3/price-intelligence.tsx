"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { BellPlus } from "lucide-react";
import { comparePrices, createPriceAlert, type PriceComparison } from "@/lib/api/marketplace";
import { getPriceIntelligence, type PriceIntelligence } from "@/lib/api/phase3";
import { useAuth } from "@/lib/auth/auth-context";
import { useI18n } from "@/lib/i18n/i18n-context";
import { errorText } from "./kit";

const BADGE: Record<string, { key: string; cls: string }> = {
  GENUINE_DISCOUNT: { key: "feature.genuineDiscount", cls: "bg-brand-light text-brand-dark" },
  MRP_INFLATED: { key: "feature.mrpInflated", cls: "bg-red-100 text-red-800" },
  NO_SPECIAL_DISCOUNT: { key: "price.noSpecial", cls: "bg-muted text-charcoal" },
  INSUFFICIENT_HISTORY: { key: "price.insufficient", cls: "bg-muted text-muted-foreground" },
};

export function PriceIntelligencePanel({ listingId, variantId }: { listingId?: string | null; variantId?: string | null }) {
  const { t, money } = useI18n();
  const { user } = useAuth();
  const [data, setData] = useState<PriceIntelligence | null>(null);
  const [cmp, setCmp] = useState<PriceComparison | null>(null);
  const [target, setTarget] = useState("");
  const [alertMsg, setAlertMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    setData(null);
    if (listingId) getPriceIntelligence(listingId).then(setData).catch(() => setData(null));
  }, [listingId]);
  useEffect(() => {
    setCmp(null);
    if (variantId) comparePrices(variantId).then(setCmp).catch(() => setCmp(null));
  }, [variantId]);

  if (!data && !cmp) return null;
  const pts = data?.history.map((h) => h.price_paise) ?? [];
  const w = 320, h = 80;
  const min = Math.min(...pts, data?.current_price_paise ?? Infinity);
  const max = Math.max(...pts, data?.current_price_paise ?? 0);
  const path = pts
    .map((p, i) => `${i === 0 ? "M" : "L"}${(i / Math.max(1, pts.length - 1)) * w},${h - ((p - min) / Math.max(1, max - min)) * (h - 8) - 4}`)
    .join(" ");
  const badge = data ? BADGE[data.badge] : undefined;

  return (
    <section aria-label={t("feature.priceHistory")} className="space-y-4 rounded-xl border bg-white p-4">
      {data && (
        <div>
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold">{t("price.historyTitle", { days: data.window_days })}</h3>
            {badge && <span className={`rounded px-2 py-0.5 text-xs font-semibold ${badge.cls}`}>{t(badge.key)}</span>}
          </div>
          {data.contains_demo_data && (
            <p className="mt-2 rounded-md border border-amber-300 bg-amber-50 px-2 py-1 text-[11px] text-amber-900">{t("price.demoNotice", { days: data.demo_days ?? 0 })}</p>
          )}
          {pts.length > 1 && (
            <svg viewBox={`0 0 ${w} ${h}`} className="mt-2 h-20 w-full text-brand" role="img" aria-label={t("price.trend")}>
              <path d={path} fill="none" stroke="currentColor" strokeWidth="2" strokeDasharray={data.contains_demo_data ? "4 3" : undefined} />
            </svg>
          )}
          <dl className="mt-2 grid grid-cols-3 gap-2 text-xs">
            <div><dt className="text-muted-foreground">{t("feature.lowestPrice")}</dt><dd className="font-semibold">{money(data.lowest_price_paise)}</dd></div>
            <div><dt className="text-muted-foreground">{t("price.highest")}</dt><dd className="font-semibold">{money(data.highest_price_paise)}</dd></div>
            <div><dt className="text-muted-foreground">{t("price.avg30")}</dt><dd className="font-semibold">{data.average_price_30d_paise ? money(data.average_price_30d_paise) : "—"}</dd></div>
          </dl>
          <p className="mt-2 text-xs text-muted-foreground">{t(`price.reason.${data.badge}`, { days: data.days_of_history })}</p>
        </div>
      )}

      {cmp && cmp.offers.length > 0 && (
        <div className="border-t pt-3">
          <h3 className="text-sm font-semibold">{t("price.compareTitle")}</h3>
          <ul className="mt-2 space-y-1 text-sm">
            {cmp.offers.map((o) => (
              <li key={o.listing_id} className="flex items-center justify-between">
                <span className={o.is_cheapest ? "font-semibold text-brand-dark" : ""}>
                  {o.retailer_name}
                  {!o.in_stock && <span className="ml-1 text-xs text-red-700">({t("common.outOfStock")})</span>}
                </span>
                <span>
                  {money(o.selling_price_paise)}
                  {o.difference_from_cheapest_paise > 0 && <span className="ml-1 text-xs text-muted-foreground">+{money(o.difference_from_cheapest_paise)}</span>}
                </span>
              </li>
            ))}
          </ul>
          {cmp.offers.length > 1 && <p className="mt-1 text-xs text-muted-foreground">{t("price.spread", { n: cmp.offers.length, spread: money(cmp.price_spread_paise) })}</p>}
        </div>
      )}

      {variantId && (
        <div className="border-t pt-3">
          <h3 className="flex items-center gap-1.5 text-sm font-semibold"><BellPlus className="h-4 w-4 text-brand" /> {t("price.alertTitle")}</h3>
          {!user ? (
            <Link href="/login" className="mt-1 inline-block text-sm text-brand underline">{t("price.signInForAlert")}</Link>
          ) : user.role !== "customer" ? null : (
            <form
              className="mt-2 flex gap-2"
              onSubmit={async (e) => {
                e.preventDefault();
                const rupees = parseFloat(target);
                if (!(rupees > 0)) return;
                try {
                  const a = await createPriceAlert(variantId, Math.round(rupees * 100));
                  setAlertMsg({ ok: true, text: a.status === "TRIGGERED" ? t("price.alertAlreadyMet") : t("price.alertSet") });
                } catch (err) {
                  setAlertMsg({ ok: false, text: errorText(err) });
                }
              }}
            >
              <label className="sr-only" htmlFor="alert-target">{t("price.targetPrice")}</label>
              <input id="alert-target" inputMode="decimal" value={target} onChange={(e) => setTarget(e.target.value)} placeholder={t("price.targetPrice")} className="h-9 w-32 rounded-md border px-2 text-sm" />
              <button type="submit" className="h-9 rounded-md bg-brand px-3 text-sm font-semibold text-white">{t("price.setAlert")}</button>
            </form>
          )}
          {alertMsg && <p className={`mt-1 text-xs ${alertMsg.ok ? "text-brand-dark" : "text-red-700"}`}>{alertMsg.text}</p>}
        </div>
      )}
    </section>
  );
}
