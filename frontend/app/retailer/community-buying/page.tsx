"use client";

import { useState } from "react";
import { retailerCampaigns, retailerCancelCampaign, retailerCreateCampaign } from "@/lib/api/phase3";
import { formatPrice } from "@/lib/utils";
import { loadMyListings } from "@/components/phase3/my-listings";
import { errorText, Notice, PageTitle, Status, useLoad } from "@/components/phase3/kit";

export default function RetailerCommunityBuyingPage() {
  const camps = useLoad(() => retailerCampaigns());
  const listings = useLoad(() => loadMyListings());
  const [f, setF] = useState({ listing_id: "", min: "5", max: "20", pct: "15", hours: "48", perMember: "5" });
  const [msg, setMsg] = useState<{ text: string; tone: "error" | "success" } | null>(null);
  return (
    <div className="space-y-4">
      <PageTitle title="Group Buys" subtitle="Offer a group price that unlocks when enough customers join." />
      <div className="flex flex-wrap items-end gap-2 rounded border bg-white p-3 text-xs">
        <select value={f.listing_id} onChange={(e) => setF({ ...f, listing_id: e.target.value })} className="rounded border p-1" aria-label="Listing">
          <option value="">Listing…</option>
          {listings.data?.map((l) => <option key={l.id} value={l.id}>{l.product_name} – {l.variant_name}</option>)}
        </select>
        {([["min", "Min members"], ["max", "Max members"], ["pct", "Discount %"], ["hours", "Hours"], ["perMember", "Max qty/member"]] as const).map(([k, label]) => (
          <label key={k}>{label}<input type="number" value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} className="ml-1 w-16 rounded border px-1" /></label>
        ))}
        <button disabled={!f.listing_id} onClick={async () => { try { await retailerCreateCampaign({ listing_id: f.listing_id, min_participants: +f.min, max_participants: +f.max, discount_percent: +f.pct, duration_hours: +f.hours, max_quantity_per_member: +f.perMember }); setMsg({ text: "Group buy launched.", tone: "success" }); await camps.reload(); } catch (e) { setMsg({ text: errorText(e), tone: "error" }); } }} className="rounded bg-blue-600 px-3 py-1 text-white disabled:opacity-40">Launch</button>
      </div>
      {msg && <Notice text={msg.text} tone={msg.tone} />}
      <Status loading={camps.loading} error={camps.error} onRetry={camps.reload} />
      <table className="w-full text-sm">
        <thead><tr className="text-left text-xs text-gray-500"><th>Campaign</th><th>Group price</th><th>Members</th><th>Status</th><th /></tr></thead>
        <tbody>
          {camps.data?.items.map((c) => (
            <tr key={c.id} className="border-t">
              <td className="py-2">{c.title}</td>
              <td>{formatPrice(c.group_price_paise)} <span className="text-xs text-gray-400">(-{c.discount_percent}%)</span></td>
              <td>{c.current_participants}/{c.min_participants}–{c.max_participants}</td>
              <td>{c.status}</td>
              <td>{c.status === "OPEN" && <button onClick={async () => { await retailerCancelCampaign(c.id); await camps.reload(); }} className="text-xs underline">Cancel</button>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
