"use client";

import { useEffect, useState } from "react";
import { BasketLoader } from "@/components/brand/basket-loader";
import { Kpi, Notice, PageHeader } from "@/components/portal/kpi";
import { getPriceDataQuality, type PriceDataQuality } from "@/lib/api/marketplace";
import { errorMessage } from "@/lib/i18n/errors";
import { useI18n } from "@/lib/i18n/i18n-context";

export default function AdminPriceIntelligencePage() {
  const { t, number, date } = useI18n();
  const [q, setQ] = useState<PriceDataQuality | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    getPriceDataQuality().then(setQ).catch((e) => setError(errorMessage(e, t)));
  }, [t]);
  return (
    <div>
      <PageHeader title={t("admin.nav.priceIntel")} subtitle={t("admin.price.subtitle")} />
      {error && <Notice kind="error">{error}</Notice>}
      {!q ? <BasketLoader /> : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            <Kpi label={t("admin.price.activeListings")} value={number(q.active_listings)} />
            <Kpi label={t("admin.price.noHistory")} value={number(q.listings_without_history)} tone={q.listings_without_history > 0 ? "warn" : "default"} hint={t("admin.price.noHistoryHint")} />
            <Kpi label={t("admin.price.demoHistory")} value={number(q.listings_with_demo_history)} tone={q.listings_with_demo_history > 0 ? "warn" : "default"} hint={t("admin.price.demoHistoryHint")} />
            <Kpi label={t("admin.price.liveTicks")} value={number(q.live_ticks)} />
            <Kpi label={t("admin.price.demoTicks")} value={number(q.demo_ticks)} />
            <Kpi label={t("admin.price.stale")} value={number(q.stale_listings_7d)} hint={t("admin.price.staleHint")} tone={q.stale_listings_7d > 0 ? "warn" : "default"} />
            <Kpi label={t("admin.price.aboveMrp")} value={number(q.selling_above_mrp)} tone={q.selling_above_mrp > 0 ? "warn" : "good"} />
            <Kpi label={t("admin.price.swings")} value={number(q.large_daily_swings)} hint={t("admin.price.swingsHint")} />
            <Kpi label={t("admin.price.alerts")} value={number(q.active_price_alerts)} />
          </div>
          <p className="mt-4 text-xs text-muted-foreground">{t("admin.price.generated", { at: date(q.generated_at, "datetime") })}</p>
        </>
      )}
    </div>
  );
}
