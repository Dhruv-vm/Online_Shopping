"use client";

import { useState } from "react";
import { retailerDemandGaps, retailerFulfillDemand } from "@/lib/api/phase3";
import { loadMyListings } from "@/components/phase3/my-listings";
import { errorText, Notice, PageTitle, Status, useLoad } from "@/components/phase3/kit";

export default function RetailerDemandGapsPage() {
  const [pin, setPin] = useState("");
  const gaps = useLoad(() => retailerDemandGaps({ pincode: pin || undefined, limit: 50 }), [pin]);
  const listings = useLoad(() => loadMyListings());
  const [choice, setChoice] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState<{ text: string; tone: "error" | "success" } | null>(null);
  return (
    <div className="space-y-4">
      <PageTitle title="Demand Gaps" subtitle="Unmet customer demand in your service area. Commit a listing to notify the shoppers who asked." />
      <input value={pin} onChange={(e) => setPin(e.target.value)} placeholder="Filter by PIN code" className="rounded border px-3 py-1 text-sm" aria-label="PIN filter" />
      <Status loading={gaps.loading} error={gaps.error} onRetry={gaps.reload} />
      {msg && <Notice text={msg.text} tone={msg.tone} />}
      <table className="w-full text-sm">
        <thead><tr className="text-left text-xs text-gray-500"><th>Demand</th><th>PIN</th><th>Shoppers</th><th>Signals</th><th>Respond</th></tr></thead>
        <tbody>
          {gaps.data?.items.map((p) => (
            <tr key={p.id} className="border-t">
              <td className="py-2">{p.display_name} <span className="text-xs text-gray-400">{p.status}</span></td>
              <td>{p.pincode ?? "Any"}</td>
              <td className="font-semibold">{p.unique_users_count}</td>
              <td>{p.total_demand_count}</td>
              <td>
                {p.responded_by_me ? <span className="text-xs text-emerald-700">Committed</span> : (
                  <div className="flex gap-1">
                    <select value={choice[p.id] ?? ""} onChange={(e) => setChoice({ ...choice, [p.id]: e.target.value })} className="max-w-[12rem] rounded border text-xs" aria-label="Listing">
                      <option value="">Choose listing…</option>
                      {listings.data?.map((l) => <option key={l.id} value={l.id}>{l.product_name} – {l.variant_name}</option>)}
                    </select>
                    <button disabled={!choice[p.id]} onClick={async () => { try { await retailerFulfillDemand(p.id, choice[p.id]); setMsg({ text: "Customers notified.", tone: "success" }); await gaps.reload(); } catch (e) { setMsg({ text: errorText(e), tone: "error" }); } }} className="rounded bg-blue-600 px-2 text-xs text-white disabled:opacity-40">Commit</button>
                  </div>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {gaps.data && gaps.data.items.length === 0 && <p className="text-sm text-gray-500">No unmet demand above the platform threshold right now.</p>}
    </div>
  );
}
