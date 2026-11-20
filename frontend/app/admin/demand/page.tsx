"use client";

import { useState } from "react";
import { adminDemandPools, adminDemandTrends, adminUpdateDemandPool } from "@/lib/api/phase3";
import { errorText, Notice, PageTitle, Status, useLoad } from "@/components/phase3/kit";

export default function AdminDemandPage() {
  const [status, setStatus] = useState("OPEN");
  const pools = useLoad(() => adminDemandPools({ status: status || undefined, limit: 100 }), [status]);
  const trends = useLoad(() => adminDemandTrends(30));
  const [err, setErr] = useState<string | null>(null);
  const max = Math.max(1, ...(trends.data?.daily.map((d) => d.signals) ?? [1]));
  return (
    <div className="space-y-4">
      <PageTitle title="Demand Intelligence" subtitle="Aggregated unmet demand, thresholds for retailer visibility and 30-day trend." />
      <div className="flex h-24 items-end gap-1 rounded border bg-white p-2" aria-label="Daily demand signals">
        {trends.data?.daily.map((d) => <div key={d.date} title={`${d.date}: ${d.signals}`} className="flex-1 bg-purple-400" style={{ height: `${(d.signals / max) * 100}%` }} />)}
      </div>
      <select value={status} onChange={(e) => setStatus(e.target.value)} className="rounded border p-1 text-sm" aria-label="Status filter">
        {["", "OPEN", "FULFILLED", "EXPIRED"].map((s) => <option key={s} value={s}>{s || "All"}</option>)}
      </select>
      <Status loading={pools.loading} error={pools.error} onRetry={pools.reload} />
      <Notice tone="error" text={err} />
      <table className="w-full text-sm">
        <thead><tr className="text-left text-xs text-gray-500"><th>Demand</th><th>PIN</th><th>Shoppers</th><th>Threshold</th><th>Offers</th><th>Status</th></tr></thead>
        <tbody>
          {pools.data?.items.map((p) => (
            <tr key={p.id} className="border-t">
              <td className="py-2">{p.display_name}</td>
              <td>{p.pincode ?? "Any"}</td>
              <td>{p.unique_users_count} <span className="text-xs text-gray-400">({p.total_demand_count})</span></td>
              <td><input type="number" min={1} defaultValue={p.visibility_threshold} onBlur={async (e) => { try { await adminUpdateDemandPool(p.id, { visibility_threshold: Number(e.target.value) }); } catch (x) { setErr(errorText(x)); } }} className="w-16 rounded border px-1" aria-label="Threshold" /></td>
              <td>{p.offers.length}</td>
              <td>
                <select defaultValue={p.status} onChange={async (e) => { try { await adminUpdateDemandPool(p.id, { status: e.target.value }); await pools.reload(); } catch (x) { setErr(errorText(x)); } }} className="rounded border text-xs" aria-label="Status">
                  {["OPEN", "FULFILLED", "EXPIRED"].map((s) => <option key={s}>{s}</option>)}
                </select>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
