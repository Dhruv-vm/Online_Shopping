"use client";

import { useState } from "react";
import { adminDemandPools, adminDemandTrends, adminUpdateDemandPool } from "@/lib/api/phase3";
import { errorText, Status, useLoad } from "@/components/phase3/kit";
import { EmptyState, Kpi, Notice, PageHeader } from "@/components/portal/kpi";
import { DataTable, Pill } from "@/components/portal/table";
import { useI18n } from "@/lib/i18n/i18n-context";

const STATUSES = ["OPEN", "FULFILLED", "EXPIRED"] as const;

export default function AdminDemandPage() {
  const { t, number } = useI18n();
  const [status, setStatus] = useState<string>("OPEN");
  const pools = useLoad(() => adminDemandPools({ status: status || undefined, limit: 100 }), [status]);
  const trends = useLoad(() => adminDemandTrends(30));
  const [err, setErr] = useState<string | null>(null);

  const daily = trends.data?.daily ?? [];
  const totalSignals = daily.reduce((s, d) => s + d.signals, 0);
  const max = Math.max(1, ...daily.map((d) => d.signals));
  const items = pools.data?.items ?? [];
  const shoppers = items.reduce((s, p) => s + p.unique_users_count, 0);
  const withOffers = items.filter((p) => p.offers.length > 0).length;

  return (
    <div>
      <PageHeader title={t("admin.nav.demand")} subtitle="Unmet demand pooled from shopper requests, the threshold at which retailers see it, and the 30-day signal trend." />

      <div className="mb-6 grid gap-3 sm:grid-cols-3">
        <Kpi label="Signals (30 days)" value={number(totalSignals)} />
        <Kpi label="Shoppers in listed pools" value={number(shoppers)} />
        <Kpi label="Pools with retailer offers" value={`${number(withOffers)} / ${number(items.length)}`} />
      </div>

      <section className="mb-6 rounded-xl border bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold text-charcoal">Daily demand signals</h2>
        <Status loading={trends.loading} error={trends.error} onRetry={trends.reload} />
        {!trends.loading && !trends.error && (totalSignals === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            No shopper has requested an unavailable product in the last 30 days. Signals appear here when customers use “Request this product” or “Notify me”.
          </p>
        ) : (
          <div className="flex h-28 items-end gap-1" role="img" aria-label={`Daily demand signals, ${totalSignals} in 30 days`}>
            {daily.map((d) => (
              <div key={d.date} title={`${d.date}: ${d.signals}`} className="flex-1 rounded-t bg-brand/70" style={{ height: `${Math.max(2, (d.signals / max) * 100)}%` }} />
            ))}
          </div>
        ))}
      </section>

      <div className="mb-3 flex items-center gap-2">
        <label htmlFor="demand-status" className="text-sm text-muted-foreground">{t("common.status")}</label>
        <select id="demand-status" value={status} onChange={(e) => setStatus(e.target.value)} className="rounded-lg border px-2 py-1 text-sm">
          <option value="">{t("common.all")}</option>
          {STATUSES.map((s) => <option key={s} value={s}>{t(`demandStatus.${s}`)}</option>)}
        </select>
      </div>

      {err && <div className="mb-3"><Notice kind="error">{err}</Notice></div>}
      <Status loading={pools.loading} error={pools.error} onRetry={pools.reload} />

      {!pools.loading && !pools.error && (items.length === 0 ? (
        <EmptyState title="No demand pools in this state" body="Pools are created automatically when shoppers ask for a product that no store currently stocks." />
      ) : (
        <DataTable head={["Demand", "PIN", "Shoppers", "Retailer threshold", "Offers", t("common.status")]}>
          {items.map((p) => (
            <tr key={p.id} className="border-t">
              <td className="px-3 py-2 font-medium">{p.display_name}</td>
              <td className="px-3 py-2">{p.pincode ?? "Any"}</td>
              <td className="px-3 py-2">{number(p.unique_users_count)} <span className="text-xs text-muted-foreground">({number(p.total_demand_count)} requests)</span></td>
              <td className="px-3 py-2">
                <input type="number" min={1} defaultValue={p.visibility_threshold} aria-label={`Threshold for ${p.display_name}`}
                  onBlur={async (e) => { try { setErr(null); await adminUpdateDemandPool(p.id, { visibility_threshold: Number(e.target.value) }); } catch (x) { setErr(errorText(x)); } }}
                  className="w-20 rounded border px-2 py-1" />
              </td>
              <td className="px-3 py-2">{p.offers.length ? <Pill tone="good">{p.offers.length}</Pill> : <span className="text-muted-foreground">0</span>}</td>
              <td className="px-3 py-2">
                <select defaultValue={p.status} aria-label={`Status for ${p.display_name}`}
                  onChange={async (e) => { try { setErr(null); await adminUpdateDemandPool(p.id, { status: e.target.value }); await pools.reload(); } catch (x) { setErr(errorText(x)); } }}
                  className="rounded border px-1 py-1 text-xs">
                  {STATUSES.map((s) => <option key={s} value={s}>{t(`demandStatus.${s}`)}</option>)}
                </select>
              </td>
            </tr>
          ))}
        </DataTable>
      ))}
    </div>
  );
}
