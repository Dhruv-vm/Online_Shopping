"use client";

import { useEffect, useState } from "react";
import { retailerBid, retailerLiveAuctions } from "@/lib/api/phase3";
import { formatPrice } from "@/lib/utils";
import { Countdown, errorText, Notice, PageTitle, rupeesToPaise, Status, useLoad } from "@/components/phase3/kit";

export default function RetailerAuctionsPage() {
  const live = useLoad(() => retailerLiveAuctions());
  const [form, setForm] = useState<Record<string, { price: string; eta: string; warranty: string }>>({});
  const [msg, setMsg] = useState<{ text: string; tone: "error" | "success" } | null>(null);
  useEffect(() => {
    const id = setInterval(() => void live.reload(), 3000);
    return () => clearInterval(id);
  }, [live.reload]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="space-y-4">
      <PageTitle title="Dukaan vs Dukaan" subtitle="Live 90-second basket auctions you can fully supply. Lowest price wins the customer's attention." />
      <Status loading={live.loading && !live.data} error={live.error} />
      {msg && <Notice text={msg.text} tone={msg.tone} />}
      {live.data?.items.map((a) => {
        const f = form[a.id] ?? { price: "", eta: "30", warranty: "" };
        return (
          <div key={a.id} className="rounded border bg-white p-3 text-sm">
            <div className="flex justify-between"><span>{a.items.map((i) => `${i.quantity}× ${i.product_name}`).join(", ")}</span><span className="font-mono text-red-600"><Countdown seconds={a.seconds_remaining} /></span></div>
            <p className="text-xs text-gray-500">PIN {a.pincode} · your list total {a.my_list_total_paise ? formatPrice(a.my_list_total_paise) : "—"} · best bid {a.best_bid_paise ? formatPrice(a.best_bid_paise) : "none"} · your best {a.my_best_bid_paise ? formatPrice(a.my_best_bid_paise) : "—"}</p>
            <div className="mt-2 flex flex-wrap gap-2 text-xs">
              <input type="number" placeholder="Bid ₹" value={f.price} onChange={(e) => setForm({ ...form, [a.id]: { ...f, price: e.target.value } })} className="w-24 rounded border px-1" aria-label="Bid amount" />
              <input type="number" placeholder="ETA min" value={f.eta} onChange={(e) => setForm({ ...form, [a.id]: { ...f, eta: e.target.value } })} className="w-20 rounded border px-1" aria-label="ETA minutes" />
              <input placeholder="Warranty (optional)" value={f.warranty} onChange={(e) => setForm({ ...form, [a.id]: { ...f, warranty: e.target.value } })} className="w-40 rounded border px-1" aria-label="Warranty note" />
              <button onClick={async () => { try { await retailerBid(a.id, { bid_price_paise: rupeesToPaise(f.price), delivery_eta_minutes: Number(f.eta), warranty_note: f.warranty || undefined }); setMsg({ text: "Bid placed.", tone: "success" }); await live.reload(); } catch (e) { setMsg({ text: errorText(e), tone: "error" }); } }} className="rounded bg-blue-600 px-3 text-white">Bid</button>
            </div>
          </div>
        );
      })}
      {live.data && live.data.items.length === 0 && <p className="text-sm text-gray-500">No live auctions you can fully supply right now. This page refreshes every 3 seconds.</p>}
    </div>
  );
}
