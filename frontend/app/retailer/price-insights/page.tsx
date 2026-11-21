"use client";

import { useEffect, useState } from "react";
import { BasketLoader } from "@/components/brand/basket-loader";
import { EmptyState, Notice, PageHeader } from "@/components/portal/kpi";
import { getRetailerPriceInsights, type RetailerPriceInsight } from "@/lib/api/marketplace";
import { errorMessage } from "@/lib/i18n/errors";
import { useI18n } from "@/lib/i18n/i18n-context";

export default function RetailerPriceInsightsPage() {
  const { t, money } = useI18n();
  const [rows, setRows] = useState<RetailerPriceInsight[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getRetailerPriceInsights().then(setRows).catch((e) => setError(errorMessage(e, t)));
  }, [t]);

  return (
    <div>
      <PageHeader title={t("priceInsights.title")} subtitle={t("priceInsights.subtitle")} />
      {error && <Notice kind="error">{error}</Notice>}
      {!rows && !error && <BasketLoader />}
      {rows && rows.length === 0 && <EmptyState title={t("priceInsights.empty")} />}
      {rows && rows.length > 0 && (
        <div className="overflow-x-auto rounded-xl border bg-white">
          <table className="w-full min-w-[720px] text-sm">
            <thead className="bg-surface text-left text-xs text-muted-foreground">
              <tr>
                <th className="px-4 py-3">{t("common.product")}</th>
                <th className="px-4 py-3 text-right">{t("priceInsights.myPrice")}</th>
                <th className="px-4 py-3 text-right">{t("priceInsights.lowestCompetitor")}</th>
                <th className="px-4 py-3 text-right">{t("priceInsights.rank")}</th>
                <th className="px-4 py-3 text-right">{t("priceInsights.history")}</th>
                <th className="px-4 py-3 text-right">{t("priceInsights.alerts")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.listing_id} className="border-t">
                  <td className="px-4 py-3">
                    <div className="font-medium">{r.product_name}</div>
                    <div className="text-xs text-muted-foreground">{r.variant_name}</div>
                  </td>
                  <td className="px-4 py-3 text-right font-semibold">{money(r.my_price_paise)}</td>
                  <td className="px-4 py-3 text-right">
                    {r.lowest_competitor_price_paise == null ? (
                      <span className="text-muted-foreground">{t("priceInsights.noCompetitors")}</span>
                    ) : (
                      <>
                        {money(r.lowest_competitor_price_paise)}
                        {r.gap_to_lowest_paise != null && r.gap_to_lowest_paise !== 0 && (
                          <span className={`ml-1 text-xs ${r.gap_to_lowest_paise > 0 ? "text-red-700" : "text-brand-dark"}`}>
                            ({r.gap_to_lowest_paise > 0 ? "+" : "−"}
                            {money(Math.abs(r.gap_to_lowest_paise))})
                          </span>
                        )}
                      </>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">{t("priceInsights.rankOf", { rank: r.my_rank, total: r.competitor_count + 1 })}</td>
                  <td className="px-4 py-3 text-right">{t("priceInsights.days", { n: r.days_of_history })}</td>
                  <td className="px-4 py-3 text-right">{r.active_price_alerts}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="mt-3 text-xs text-muted-foreground">{t("priceInsights.note")}</p>
    </div>
  );
}
