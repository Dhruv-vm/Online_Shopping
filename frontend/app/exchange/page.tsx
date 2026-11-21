"use client";

import Link from "next/link";
import { useState } from "react";
import { acceptRfqBid, cancelRfq, createRfq, myRfqs, type ManifestItem } from "@/lib/api/phase3";
import { useI18n } from "@/lib/i18n/i18n-context";
import { formatPrice } from "@/lib/utils";
import { errorText, Notice, PageTitle, rupeesToPaise, Status, useLoad } from "@/components/phase3/kit";

export default function ExchangePage() {
  const { t } = useI18n();
  const { data, loading, error, reload } = useLoad(() => myRfqs());
  const [title, setTitle] = useState("");
  const [pincode, setPincode] = useState("");
  const [budget, setBudget] = useState("");
  const [items, setItems] = useState<ManifestItem[]>([{ name: "", quantity: 1 }]);
  const [msg, setMsg] = useState<{ text: string; tone: "error" | "success" } | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setMsg(null);
    try {
      await createRfq({
        title,
        delivery_pincode: pincode,
        budget_limit_paise: budget ? rupeesToPaise(budget) : undefined,
        items: items.filter((i) => i.name.trim()),
      });
      setTitle(""); setItems([{ name: "", quantity: 1 }]);
      setMsg({ text: "Request sent to nearby retailers.", tone: "success" });
      await reload();
    } catch (err) {
      setMsg({ text: errorText(err), tone: "error" });
    }
  };

  return (
    <div className="container mx-auto max-w-4xl px-4 py-8">
      <PageTitle title={t("nav.exchange")} subtitle="Describe what you need; local shops send you competing offers." />
      <form onSubmit={submit} className="mb-8 space-y-3 rounded-lg border bg-white p-4">
        <div className="grid gap-3 sm:grid-cols-3">
          <input required minLength={3} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Party supplies for 40" className="rounded border px-3 py-2 text-sm sm:col-span-3" aria-label="Title" />
          <input required pattern="[1-9][0-9]{5}" value={pincode} onChange={(e) => setPincode(e.target.value)} placeholder="Delivery PIN code" className="rounded border px-3 py-2 text-sm" aria-label="PIN code" />
          <input type="number" min={1} value={budget} onChange={(e) => setBudget(e.target.value)} placeholder="Budget ₹ (optional)" className="rounded border px-3 py-2 text-sm" aria-label="Budget" />
        </div>
        {items.map((it, i) => (
          <div key={i} className="flex gap-2">
            <input required={i === 0} value={it.name} onChange={(e) => setItems(items.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))} placeholder="Item" className="flex-1 rounded border px-3 py-2 text-sm" aria-label={`Item ${i + 1}`} />
            <input type="number" min={1} max={10} value={it.quantity} onChange={(e) => setItems(items.map((x, j) => (j === i ? { ...x, quantity: Number(e.target.value) } : x)))} className="w-20 rounded border px-2 py-2 text-sm" aria-label={`Quantity ${i + 1}`} />
          </div>
        ))}
        <div className="flex gap-2">
          {items.length < 20 && <button type="button" onClick={() => setItems([...items, { name: "", quantity: 1 }])} className="rounded border px-3 py-1 text-sm">+ Item</button>}
          <button type="submit" className="rounded bg-emerald-600 px-4 py-1 text-sm text-white">Request offers</button>
        </div>
        {msg && <Notice text={msg.text} tone={msg.tone} />}
      </form>

      <h2 className="mb-3 text-lg font-semibold">My requests</h2>
      <Status loading={loading} error={error} onRetry={reload} />
      <div className="space-y-4">
        {data?.items.map((r) => (
          <div key={r.id} className="rounded-lg border bg-white p-4">
            <div className="flex justify-between">
              <span className="font-medium">{r.title}</span>
              <span className="text-xs font-semibold">{r.status}</span>
            </div>
            <p className="text-xs text-gray-500">PIN {r.delivery_pincode} · {r.items.map((i) => `${i.quantity}× ${i.name}`).join(", ")}</p>
            {(r.bids ?? []).length === 0 ? (
              <p className="mt-2 text-sm text-gray-500">No offers yet.</p>
            ) : (
              <table className="mt-3 w-full text-sm">
                <thead><tr className="text-left text-xs text-gray-500"><th>Store</th><th>Price</th><th>Items</th><th>ETA</th><th /></tr></thead>
                <tbody>
                  {r.bids!.map((b) => (
                    <tr key={b.id} className="border-t">
                      <td>{b.retailer_name} <span className="text-xs text-gray-400">★{b.retailer_rating.toFixed(1)}</span></td>
                      <td className="font-semibold">{formatPrice(b.bid_amount_paise)}</td>
                      <td>{b.items_covered}/{b.items_requested}</td>
                      <td>{b.estimated_delivery_hours}h</td>
                      <td className="text-right">
                        {r.status === "BIDDING_OPEN" && b.status === "SUBMITTED" ? (
                          <button onClick={async () => { try { const res = await acceptRfqBid(r.id, b.id); setMsg({ text: res.message, tone: "success" }); await reload(); } catch (e) { setMsg({ text: errorText(e), tone: "error" }); } }} className="rounded bg-emerald-600 px-2 py-0.5 text-xs text-white">Accept</button>
                        ) : <span className="text-xs">{b.status}</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <div className="mt-2 flex gap-3 text-xs">
              {r.status === "AWARDED" && <Link href="/cart" className="text-emerald-700 underline">Go to basket</Link>}
              {r.status === "BIDDING_OPEN" && <button onClick={async () => { await cancelRfq(r.id); await reload(); }} className="underline">Cancel request</button>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
