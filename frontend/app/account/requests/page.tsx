"use client";

import Link from "next/link";
import { ProtectedRoute } from "@/components/auth/protected-route";
import { Status, useLoad } from "@/components/phase3/kit";
import { EmptyState, PageHeader } from "@/components/portal/kpi";
import { Pill } from "@/components/portal/table";
import { myDemandRequests } from "@/lib/api/phase3";
import { useI18n } from "@/lib/i18n/i18n-context";

function Requests() {
  const { t, money, date } = useI18n();
  const reqs = useLoad(() => myDemandRequests());
  return (
    <div className="container-page max-w-4xl py-8">
      <PageHeader title={t("nav.myRequests")} subtitle={t("requests.subtitle")} />
      <Status loading={reqs.loading} error={reqs.error} onRetry={reqs.reload} />
      {reqs.data && reqs.data.items.length === 0 && (
        <EmptyState title={t("requests.empty")} body={t("requests.emptyBody")} action={<Link href="/products" className="text-sm text-brand underline">{t("nav.catalogue")}</Link>} />
      )}
      <ul className="space-y-3">
        {reqs.data?.items.map((p) => (
          <li key={p.id} className="rounded-xl border bg-white p-4 text-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-semibold">{p.display_name}</p>
              <Pill tone={p.status === "FULFILLED" ? "good" : p.status === "OPEN" ? "warn" : "neutral"}>{t(`demandStatus.${p.status}`)}</Pill>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              {t("requests.shoppers", { n: p.unique_users_count })}
              {p.pincode ? ` · PIN ${p.pincode}` : ""} · {t("requests.lastActivity", { at: date(p.last_signal_at) })}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              {p.unique_users_count >= p.visibility_threshold ? t("requests.visible") : t("requests.notYetVisible", { n: p.visibility_threshold - p.unique_users_count })}
            </p>
            {p.offers.length > 0 && (
              <ul className="mt-2 space-y-1 border-t pt-2">
                {p.offers.map((o) => (
                  <li key={`${o.retailer_id}-${o.created_at}`} className="flex items-center justify-between">
                    <span>{o.retailer_name}</span>
                    <span>
                      {money(o.offered_price_paise)}{" "}
                      <Link href={`/search?q=${encodeURIComponent(p.display_name)}`} className="ml-2 text-brand underline">{t("requests.view")}</Link>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function MyRequestsPage() {
  return (
    <ProtectedRoute>
      <Requests />
    </ProtectedRoute>
  );
}
