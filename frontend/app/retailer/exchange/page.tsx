"use client";

import { useState } from "react";
import { retailerOpenRfqs, retailerSubmitRfqBid, type ExchangeRequest } from "@/lib/api/phase3";
import { formatPrice } from "@/lib/utils";
import { loadMyListings } from "@/components/phase3/my-listings";
import { errorText, Notice, PageTitle, rupeesToPaise, Status, useLoad } from "@/components/phase3/kit";

function BidForm({ r, listings, onDone }: { r: ExchangeRequest; listings: { id: string; label: string; price: number }[]; onDone: () => void }) {
  const [lines, setLines] = useState<Record<number, { listing_id: string; price: string }>>({});
  const [eta, setEta] = useState("4");
  const [err, setErr] = useState<string | null>(null);
  const total = Object.entries(lines).reduce((s, [i, l]) => s + (l.listing_id && l.price ? rupeesToPaise(l.price) * r.items[Number(i)].quantity : 0), 0);
  return (
    <div className="mt-2 space-y-2">
      {r.items.map((it, i) => (
        <div key={i} className="flex flex-wrap items-center gap-2 text-xs">
          <span className="w-40">{it.quantity}× {it.name}</span>
          <select value={lines[i]?.listing_id ?? ""} onChange={(e) => setLines({ ...lines, [i]: { listing_id: e.target.value, price: String((listings.find((l) => l.id === e.target.value)?.price ?? 0) / 100) } })} className="rounded border" aria-label={`Listing for ${it.name}`}>
            <option value="">Not offered</option>
            {listings.map((l) => <option key={l.id} value={l.id}>{l.label}</option>)}
          </select>
          {lines[i]?.listing_id && <input type="number" min={0.01} step="0.01" value={lines[i].price} onChange={(e) => setLines({ ...lines, [i]: { ...lines[i], price: e.target.value } })} className="w-24 rounded border px-1" aria-label={`Unit price for ${it.name}`} />}
        </div>
      ))}
      <div className="flex items-center gap-2 text-xs">
        ETA hours <input type="number" min={1} value={eta} onChange={(e) => setEta(e.target.value)} className="w-16 rounded border px-1" aria-label="ETA hours" />
        <span>Bid total: <b>{formatPrice(total)}</b>{r.budget_limit_paise ? ` (budget ${formatPrice(r.budget_limit_paise)})` : ""}</span>
        <button onClick={async () => {
          setErr(null);
          try {
            await retailerSubmitRfqBid(r.id, {
              lines: Object.entries(lines).filter(([, l]) => l.listing_id).map(([i, l]) => ({ manifest_index: Number(i), listing_id: l.listing_id, unit_price_paise: rupeesToPaise(l.price) })),
              estimated_delivery_hours: Number(eta),
            });
            onDone();
          } catch (e) { setErr(errorText(e)); }
        }} disabled={!Object.values(lines).some((l) => l.listing_id)} className="rounded bg-blue-600 px-3 py-1 text-white disabled:opacity-40">{r.my_bid ? "Revise bid" : "Submit bid"}</button>
        {!Object.values(lines).some((l) => l.listing_id) && <span className="text-gray-500">Choose one of your listings for at least one item to bid.</span>}
      </div>
      <Notice tone="error" text={err} />
    </div>
  );
}

export default function RetailerExchangePage() {
  const rfqs = useLoad(() => retailerOpenRfqs());
  const listings = useLoad(async () => (await loadMyListings()).map((l) => ({ id: l.id, label: `${l.product_name} – ${l.variant_name} (${formatPrice(l.selling_price_paise)})`, price: l.selling_price_paise })));
  return (
    <div className="space-y-4">
      <PageTitle title="Community Exchange (RFQs)" subtitle="Open customer requests in your area. Bids cannot exceed your listed prices." />
      <Status loading={rfqs.loading} error={rfqs.error} onRetry={rfqs.reload} />
      {rfqs.data?.items.map((r) => (
        <div key={r.id} className="rounded border bg-white p-3">
          <div className="flex justify-between text-sm"><b>{r.title}</b><span className="text-xs">PIN {r.delivery_pincode} · {r.bid_count} bid(s)</span></div>
          {r.my_bid && <p className="text-xs text-blue-700">Your bid: {formatPrice(r.my_bid.bid_amount_paise)} ({r.my_bid.status})</p>}
          <BidForm r={r} listings={listings.data ?? []} onDone={rfqs.reload} />
        </div>
      ))}
      {rfqs.data && rfqs.data.items.length === 0 && <p className="text-sm text-gray-500">No open requests in your service area.</p>}
    </div>
  );
}
