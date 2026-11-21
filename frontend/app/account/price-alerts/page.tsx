"use client";

import { ProtectedRoute } from "@/components/auth/protected-route";
import { errorText, Status, useLoad } from "@/components/phase3/kit";
import { EmptyState, PageHeader } from "@/components/portal/kpi";
import { cancelPriceAlert, listPriceAlerts } from "@/lib/api/marketplace";
import { useI18n } from "@/lib/i18n/i18n-context";

function Alerts() {
  const { t, money, date } = useI18n();
  const alerts = useLoad(() => listPriceAlerts());
  return (
    <div className="container-page max-w-4xl py-8">
      <PageHeader title={t("nav.priceAlerts")} subtitle={t("alerts.subtitle")} />
      <Status loading={alerts.loading} error={alerts.error} onRetry={alerts.reload} />
      {alerts.data && alerts.data.length === 0 && <EmptyState title={t("alerts.empty")} body={t("alerts.emptyBody")} />}
      <ul className="space-y-3">
        {alerts.data?.map((a) => (
          <li key={a.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-white p-4 text-sm">
            <div>
              <p className="font-semibold">{a.product_name}</p>
              <p className="text-xs text-muted-foreground">{a.variant_name}</p>
              <p className="mt-1">
                {t("alerts.target")}: <strong>{money(a.target_price_paise)}</strong> · {t("alerts.bestNow")}:{" "}
                {a.current_best_price_paise != null ? money(a.current_best_price_paise) : t("product.unavailable")}
              </p>
              {a.status === "TRIGGERED" && a.triggered_price_paise != null && (
                <p className="mt-1 text-xs font-semibold text-brand-dark">{t("alerts.triggered", { price: money(a.triggered_price_paise), at: a.triggered_at ? date(a.triggered_at, "datetime") : "" })}</p>
              )}
            </div>
            {a.status === "ACTIVE" && (
              <button type="button" className="text-xs text-red-700 underline" onClick={async () => { try { await cancelPriceAlert(a.id); await alerts.reload(); } catch (e) { alerts.setError(errorText(e)); } }}>
                {t("alerts.remove")}
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function PriceAlertsPage() {
  return (
    <ProtectedRoute>
      <Alerts />
    </ProtectedRoute>
  );
}
