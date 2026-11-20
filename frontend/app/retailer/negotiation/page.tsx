"use client";

import { useState } from "react";
import { deleteNegotiationRule, listNegotiationRules, upsertNegotiationRule } from "@/lib/api/phase3";
import { formatPrice } from "@/lib/utils";
import { loadMyListings } from "@/components/phase3/my-listings";
import { errorText, Notice, PageTitle, rupeesToPaise, Status, useLoad } from "@/components/phase3/kit";

export default function RetailerNegotiationPage() {
  const rules = useLoad(() => listNegotiationRules());
  const listings = useLoad(() => loadMyListings());
  const [f, setF] = useState({ listing_id: "", pct: "5", floor: "", bundleQty: "", bundlePct: "0" });
  const [msg, setMsg] = useState<{ text: string; tone: "error" | "success" } | null>(null);
  const name = (id: string | null) => (id ? listings.data?.find((l) => l.id === id)?.product_name ?? id.slice(0, 8) : "All products (storewide)");
  return (
    <div className="space-y-4">
      <PageTitle title="AI Negotiator Rules" subtitle="The assistant never offers below these limits, and never reveals your floor to customers." />
      <div className="flex flex-wrap items-end gap-2 rounded border bg-white p-3 text-xs">
        <select value={f.listing_id} onChange={(e) => setF({ ...f, listing_id: e.target.value })} className="rounded border p-1" aria-label="Scope">
          <option value="">Storewide</option>
          {listings.data?.map((l) => <option key={l.id} value={l.id}>{l.product_name} – {l.variant_name}</option>)}
        </select>
        <label>Max auto discount %<input type="number" min={0} max={50} value={f.pct} onChange={(e) => setF({ ...f, pct: e.target.value })} className="ml-1 w-14 rounded border px-1" /></label>
        {f.listing_id && <label>Floor ₹<input type="number" value={f.floor} onChange={(e) => setF({ ...f, floor: e.target.value })} className="ml-1 w-20 rounded border px-1" /></label>}
        <label>Bundle qty ≥<input type="number" min={2} max={10} value={f.bundleQty} onChange={(e) => setF({ ...f, bundleQty: e.target.value })} className="ml-1 w-14 rounded border px-1" /></label>
        <label>Extra %<input type="number" min={0} max={20} value={f.bundlePct} onChange={(e) => setF({ ...f, bundlePct: e.target.value })} className="ml-1 w-14 rounded border px-1" /></label>
        <button onClick={async () => {
          try {
            await upsertNegotiationRule({
              listing_id: f.listing_id || null,
              max_auto_discount_percent: +f.pct,
              min_floor_price_paise: f.listing_id && f.floor ? rupeesToPaise(f.floor) : null,
              bundle_quantity_threshold: f.bundleQty ? +f.bundleQty : null,
              bundle_extra_discount_percent: +f.bundlePct || 0,
              is_active: true,
            });
            setMsg({ text: "Rule saved.", tone: "success" });
            await rules.reload();
          } catch (e) { setMsg({ text: errorText(e), tone: "error" }); }
        }} className="rounded bg-blue-600 px-3 py-1 text-white">Save rule</button>
      </div>
      {msg && <Notice text={msg.text} tone={msg.tone} />}
      <Status loading={rules.loading} error={rules.error} onRetry={rules.reload} />
      <ul className="space-y-2 text-sm">
        {rules.data?.map((r) => (
          <li key={r.id} className="flex justify-between rounded border bg-white p-2">
            <span>{name(r.listing_id)} · up to {r.max_auto_discount_percent}%{r.min_floor_price_paise ? ` · floor ${formatPrice(r.min_floor_price_paise)}` : ""}{r.bundle_quantity_threshold ? ` · +${r.bundle_extra_discount_percent}% at ${r.bundle_quantity_threshold}+` : ""}</span>
            <button onClick={async () => { await deleteNegotiationRule(r.id); await rules.reload(); }} className="text-xs underline">Delete</button>
          </li>
        ))}
      </ul>
    </div>
  );
}
