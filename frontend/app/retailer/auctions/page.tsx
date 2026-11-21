"use client";

import { useEffect, useState } from "react";
import { retailerBid, retailerLiveAuctions, retailerRecentAuctions, retailerSimulateBid, type Auction } from "@/lib/api/phase3";
import { useLiveState, useLiveUpdates } from "@/lib/realtime";
import { formatPrice } from "@/lib/utils";
import { Countdown, errorText, Notice, PageTitle, rupeesToPaise, Status, useLoad } from "@/components/phase3/kit";
import { AuctionDemoSimulation } from "@/components/retailer/auction-demo-simulation";

const OUTCOME: Record<string, { text: string; cls: string }> = {
  WON: { text: "You won — the shopper chose your bid", cls: "text-green-700" },
  NOT_SELECTED: { text: "Not selected — the shopper chose another store", cls: "text-red-700" },
  AWAITING_CHOICE: { text: "Bidding closed — shopper is choosing", cls: "text-amber-700" },
  CLOSED: { text: "Closed", cls: "text-gray-600" },
};

function Position({ a }: { a: Auction }) {
  if (!a.my_rank) return <span className="text-gray-600">You have not bid · {a.competing_stores ?? 0} store(s) bidding</span>;
  if (a.is_winning) return <span className="font-semibold text-green-700">You are winning · position 1 of {a.competing_stores}</span>;
  return <span className="font-semibold text-red-700">Outbid · position {a.my_rank} of {a.competing_stores}</span>;
}

export default function RetailerAuctionsPage() {
  const live = useLoad(() => retailerLiveAuctions());
  const recent = useLoad(() => retailerRecentAuctions());
  const liveState = useLiveState();
  const [form, setForm] = useState<Record<string, { price: string; eta: string; warranty: string }>>({});
  const [msg, setMsg] = useState<{ text: string; tone: "error" | "success" } | null>(null);

  // New auctions, bids, closures and awards arrive as live notices; a fast
  // fallback keeps the page synchronized even if the live connection drops.
  useLiveUpdates(["auction.", "retailer.auction"], () => {
    void live.refresh();
    void recent.refresh();
  }, { fallbackMs: liveState === "live" ? 5000 : 2000 });

  // Refresh right after the soonest countdown reaches zero so closure shows promptly.
  const soonest = Math.min(...(live.data?.items.map((a) => a.seconds_remaining) ?? [Infinity]));
  useEffect(() => {
    if (!Number.isFinite(soonest)) return;
    const id = setTimeout(() => {
      void live.refresh();
      void recent.refresh();
    }, (soonest + 1) * 1000);
    return () => clearTimeout(id);
  }, [soonest, live.data]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="space-y-4">
      <PageTitle title="Dukaan vs Dukaan" subtitle="Live 90-second basket auctions you can fully supply. Lowest price wins the customer's attention." />
      <p className="text-xs text-gray-500" aria-live="polite">
        {liveState === "live" ? <span className="text-green-700">● Live updates on</span> : <span>○ Reconnecting — refreshing every 10 seconds</span>}
      </p>
      <Status loading={live.loading && !live.data} error={live.error} />
      {msg && <Notice text={msg.text} tone={msg.tone} />}
      {live.data?.items.map((a) => {
        const f = form[a.id] ?? { price: "", eta: "30", warranty: "" };
        return (
          <div key={a.id} className={`rounded border bg-white p-3 text-sm ${a.outbid ? "border-red-300" : a.is_winning ? "border-green-300" : ""}`}>
            <div className="flex justify-between"><span>{a.items.map((i) => `${i.quantity}× ${i.product_name}${i.variant_name ? ` (${i.variant_name})` : ""}`).join(", ")}</span><span className="font-mono text-red-600"><Countdown seconds={a.seconds_remaining} /></span></div>
            <p className="text-xs text-gray-500">PIN {a.pincode} · your list total {a.my_list_total_paise ? formatPrice(a.my_list_total_paise) : "—"} · current winning bid {a.best_bid_paise ? formatPrice(a.best_bid_paise) : "none"} · your best {a.my_best_bid_paise ? formatPrice(a.my_best_bid_paise) : "—"}</p>
            <p className="mt-1 text-xs"><Position a={a} /></p>
            {a.bid_ladder && a.bid_ladder.length > 0 && (
              <details className="mt-1 text-xs text-gray-600">
                <summary>Bid history ({a.bid_ladder.length}) — prices only, stores are not named</summary>
                <ol className="mt-1 max-h-28 overflow-auto">
                  {[...a.bid_ladder].reverse().map((b, i) => (
                    <li key={`${b.at}-${i}`}>{b.mine ? "You" : "Another store"} · {formatPrice(b.price_paise)} · {new Date(b.at).toLocaleTimeString()}</li>
                  ))}
                </ol>
              </details>
            )}
            <div className="mt-2 flex flex-wrap gap-2 text-xs">
              <input type="number" placeholder="Bid ₹" value={f.price} onChange={(e) => setForm({ ...form, [a.id]: { ...f, price: e.target.value } })} className="w-24 rounded border px-1" aria-label="Bid amount" />
              <input type="number" placeholder="ETA min" value={f.eta} onChange={(e) => setForm({ ...form, [a.id]: { ...f, eta: e.target.value } })} className="w-20 rounded border px-1" aria-label="ETA minutes" />
              <input placeholder="Warranty (optional)" value={f.warranty} onChange={(e) => setForm({ ...form, [a.id]: { ...f, warranty: e.target.value } })} className="w-40 rounded border px-1" aria-label="Warranty note" />
              <button onClick={async () => { try { await retailerBid(a.id, { bid_price_paise: rupeesToPaise(f.price), delivery_eta_minutes: Number(f.eta), warranty_note: f.warranty || undefined }); setMsg({ text: "Bid placed.", tone: "success" }); setForm({ ...form, [a.id]: { ...f, price: "" } }); await live.refresh(); } catch (e) { setMsg({ text: errorText(e), tone: "error" }); } }} className="rounded bg-blue-600 px-3 text-white hover:bg-blue-700">Bid</button>
              <button onClick={async () => { try { await retailerSimulateBid(a.id); setMsg({ text: "Simulated competitive bid placed.", tone: "success" }); await live.refresh(); } catch (e) { setMsg({ text: errorText(e), tone: "error" }); } }} className="rounded bg-amber-600 px-3 text-white hover:bg-amber-700" title="Simulate competitive offer for live auction">Simulate Bid</button>
            </div>
          </div>
        );
      })}
      {live.data && live.data.items.length === 0 && <p className="text-sm text-gray-500">No live auctions you can fully supply right now. New auctions in your service area appear here automatically.</p>}

      {recent.data && recent.data.items.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-sm font-semibold">Recent results (last 24 hours)</h2>
          {recent.data.items.map((a) => {
            const o = OUTCOME[a.my_outcome ?? "CLOSED"] ?? OUTCOME.CLOSED;
            return (
              <div key={a.id} className="rounded border bg-white p-2 text-xs">
                <span>{a.items.map((i) => `${i.quantity}× ${i.product_name}`).join(", ")}</span>
                <span className="text-gray-500"> · PIN {a.pincode} · your best {a.my_best_bid_paise ? formatPrice(a.my_best_bid_paise) : "—"} · lowest bid {a.best_bid_paise ? formatPrice(a.best_bid_paise) : "—"}</span>
                <p className={`font-semibold ${o.cls}`}>{o.text}</p>
              </div>
            );
          })}
        </div>
      )}

      <AuctionDemoSimulation
        activeAuctions={live.data?.items ?? []}
        onSimulateBid={async (aid) => {
          try {
            await retailerSimulateBid(aid);
            setMsg({ text: "Simulated competitive bid placed.", tone: "success" });
            await live.refresh();
          } catch (e) {
            setMsg({ text: errorText(e), tone: "error" });
          }
        }}
      />
    </div>
  );
}
