"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { acceptAuctionBid, getAuctionLive, startAuction, type Auction } from "@/lib/api/phase3";
import { useI18n } from "@/lib/i18n/i18n-context";
import { formatPrice } from "@/lib/utils";
import { Countdown, errorText, Notice, PageTitle } from "@/components/phase3/kit";

export default function AuctionsPage() {
  const { t } = useI18n();
  const [pincode, setPincode] = useState("");
  const [auction, setAuction] = useState<Auction | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  // Poll every 2s while live (EventSource is also available: auctionEventStreamPath).
  useEffect(() => {
    if (!auction || auction.status !== "ACTIVE") return;
    const id = setInterval(async () => {
      try {
        setAuction(await getAuctionLive(auction.id));
      } catch (e) {
        setErr(errorText(e));
      }
    }, 2000);
    return () => clearInterval(id);
  }, [auction]);

  return (
    <div className="container mx-auto max-w-3xl px-4 py-8">
      <PageTitle title={t("nav.auctions")} subtitle="Let nearby shops compete for your whole basket for 90 seconds. You choose the winner." />
      {!auction && (
        <form onSubmit={async (e) => { e.preventDefault(); setErr(null); try { setAuction(await startAuction(pincode)); } catch (x) { setErr(errorText(x)); } }} className="flex gap-2">
          <input required pattern="[1-9][0-9]{5}" value={pincode} onChange={(e) => setPincode(e.target.value)} placeholder="Delivery PIN code" className="rounded border px-3 py-2 text-sm" aria-label="PIN code" />
          <button className="rounded bg-emerald-600 px-4 py-2 text-sm text-white">Start 90-second auction</button>
        </form>
      )}
      <Notice text={err} tone="error" />
      {auction && (
        <div className="rounded-lg border bg-white p-4">
          <div className="flex items-center justify-between">
            <span className="text-sm">Basket list price: <b>{formatPrice(auction.reference_total_paise)}</b></span>
            {auction.status === "ACTIVE" ? <span className="text-2xl font-bold text-red-600"><Countdown seconds={auction.seconds_remaining} /></span> : <span className="font-semibold">{auction.status}</span>}
          </div>
          <p className="mt-1 text-xs text-gray-500">{auction.items.map((i) => `${i.quantity}× ${i.product_name}`).join(", ")}</p>
          <ul className="mt-4 space-y-2">
            {(auction.bids ?? []).map((b) => (
              <li key={b.id} className={`flex items-center justify-between rounded border p-3 ${b.rank === 1 ? "border-emerald-400 bg-emerald-50" : ""}`}>
                <div>
                  <p className="font-medium">#{b.rank} {b.retailer_name} <span className="text-xs text-gray-500">★{b.retailer_rating.toFixed(1)}</span></p>
                  <p className="text-xs text-gray-500">ETA {b.delivery_eta_minutes} min{b.warranty_note ? ` · ${b.warranty_note}` : ""}</p>
                </div>
                <div className="text-right">
                  <p className="font-bold">{formatPrice(b.bid_price_paise)}</p>
                  <p className="text-xs text-emerald-700">save {formatPrice(Math.max(0, b.savings_paise))}</p>
                  {auction.status === "COMPLETED" && (
                    <button onClick={async () => { try { const r = await acceptAuctionBid(auction.id, b.id); setAuction(r.auction); setDone(r.message); } catch (e) { setErr(errorText(e)); } }} className="mt-1 rounded bg-emerald-600 px-2 py-0.5 text-xs text-white">Choose</button>
                  )}
                </div>
              </li>
            ))}
          </ul>
          {auction.status === "ACTIVE" && (auction.bids ?? []).length === 0 && <p className="mt-4 text-sm text-gray-500">Waiting for shops to bid…</p>}
          {auction.status === "NO_BIDS" && <p className="mt-4 text-sm">No shop bid this time. Your basket is unchanged.</p>}
          {done && <><Notice text={done} tone="success" /><Link href="/checkout" className="text-sm text-emerald-700 underline">Proceed to checkout</Link></>}
        </div>
      )}
    </div>
  );
}
