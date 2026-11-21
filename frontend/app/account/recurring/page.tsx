"use client";

import { useState } from "react";
import Link from "next/link";
import { ProtectedRoute } from "@/components/auth/protected-route";
import { AccountNav } from "@/components/account/account-nav";
import { errorText, Notice, Status, useLoad } from "@/components/phase3/kit";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiClient } from "@/lib/api/client";
import {
  checkRecurring, createRecurring, listRecurring, loadRecurring, recurringAction, updateRecurring,
  type PreOrderCheck, type RecurringBasket,
} from "@/lib/api/recurring";
import { formatPrice } from "@/lib/utils";

const STATUS: Record<string, string> = { ACTIVE: "Active", PAUSED: "Paused", CANCELLED: "Cancelled", ENDED: "Ended" };

function BasketCard({ b, onChange, setMsg }: { b: RecurringBasket; onChange: () => void; setMsg: (m: { text: string; tone: "error" | "success" }) => void }) {
  const [check, setCheck] = useState<PreOrderCheck | null>(null);
  const [editing, setEditing] = useState(false);
  const [day, setDay] = useState(String(b.day_of_month));
  const [end, setEnd] = useState(b.end_date ?? "");
  const [qty, setQty] = useState<Record<string, string>>(Object.fromEntries(b.items.map((i) => [i.listing_id, String(i.quantity)])));
  const run = async (fn: () => Promise<unknown>, ok?: string) => {
    try {
      await fn();
      if (ok) setMsg({ text: ok, tone: "success" });
      onChange();
    } catch (e) {
      setMsg({ text: errorText(e), tone: "error" });
    }
  };
  const live = b.status === "ACTIVE" || b.status === "PAUSED";
  return (
    <div className="space-y-2 rounded-xl border bg-white p-4 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-semibold">{b.name}</p>
        <span className="text-xs">{STATUS[b.status]} · autopay off</span>
      </div>
      <p className="text-xs text-muted-foreground">
        Every month on day {b.day_of_month} · from {b.start_date}{b.end_date ? ` to ${b.end_date}` : ""}
        {b.next_run_date ? ` · next: ${b.next_run_date}` : ""}
        {b.skip_dates.length > 0 ? ` · skipped: ${b.skip_dates.join(", ")}` : ""}
      </p>
      <ul className="text-xs">
        {b.items.map((i) => (
          <li key={i.listing_id}>
            {editing ? (
              <input type="number" min={0} value={qty[i.listing_id] ?? ""} onChange={(e) => setQty({ ...qty, [i.listing_id]: e.target.value })} className="mr-2 w-14 rounded border px-1" aria-label={`Quantity of ${i.product_name}`} />
            ) : (
              `${i.quantity}× `
            )}
            {i.product_name}{i.variant_name ? ` (${i.variant_name})` : ""} · {i.retailer_name} · set up at {formatPrice(i.unit_price_paise_at_setup)}
          </li>
        ))}
      </ul>
      {editing && (
        <div className="flex flex-wrap gap-2 text-xs">
          <label className="flex items-center gap-1">Day <Input type="number" min={1} max={28} value={day} onChange={(e) => setDay(e.target.value)} className="h-8 w-16" /></label>
          <label className="flex items-center gap-1">End date <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} className="h-8" /></label>
          <Button size="sm" onClick={() => run(() => updateRecurring(b.id, {
            day_of_month: Number(day),
            ...(end ? { end_date: end } : { clear_end_date: true }),
            quantities: Object.fromEntries(Object.entries(qty).map(([k, v]) => [k, Math.max(0, Number(v) || 0)])),
          }).then(() => setEditing(false)), "Schedule updated.")}>Save</Button>
          <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>Close</Button>
        </div>
      )}
      {live && (
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" onClick={async () => { try { setCheck(await checkRecurring(b.id)); } catch (e) { setMsg({ text: errorText(e), tone: "error" }); } }}>Check prices &amp; stock</Button>
          <Button size="sm" variant="outline" onClick={() => setEditing(!editing)}>Edit</Button>
          {b.status === "ACTIVE" && <Button size="sm" variant="outline" onClick={() => run(() => recurringAction(b.id, "skip"), "Next month skipped.")}>Skip next month</Button>}
          {b.status === "ACTIVE" ? (
            <Button size="sm" variant="outline" onClick={() => run(() => recurringAction(b.id, "pause"), "Paused.")}>Pause</Button>
          ) : (
            <Button size="sm" variant="outline" onClick={() => run(() => recurringAction(b.id, "resume"), "Resumed.")}>Resume</Button>
          )}
          <Button size="sm" variant="ghost" onClick={() => void run(() => recurringAction(b.id, "cancel"), "Recurring basket cancelled.")}>Cancel</Button>
        </div>
      )}
      {check && (
        <div className="space-y-1 rounded border p-2 text-xs" aria-live="polite">
          <p className="font-semibold">Pre-order check {check.scheduled_for ? `for ${check.scheduled_for}` : ""} · {new Date(check.checked_at).toLocaleString()}</p>
          {check.lines.map((l) => (
            <p key={l.listing_id} className={l.status === "OK" ? "" : l.status === "PRICE_CHANGED" ? "text-amber-700" : "text-red-600"}>
              {l.quantity}× {l.product_name}: {l.final_unit_price_paise != null ? formatPrice(l.final_unit_price_paise) : "—"} each
              {l.offers.length > 0 && ` (offer: ${l.offers.join(", ")})`}
              {l.status !== "OK" && ` · ${l.status === "PRICE_CHANGED" ? `was ${formatPrice(l.previous_unit_price_paise)}` : l.note}`}
            </p>
          ))}
          <p>
            Updated items total <strong>{formatPrice(check.items_total_paise)}</strong> (was {formatPrice(check.previous_total_paise)} at set-up prices)
          </p>
          {!check.delivery_address_set && <p className="text-amber-700">No delivery address set: delivery is checked at checkout.</p>}
          <p className="text-muted-foreground">{check.note}</p>
          {check.orderable_lines > 0 && (
            <Button size="sm" onClick={() => run(async () => { const r = await loadRecurring(b.id); setMsg({ text: r.message, tone: "success" }); })}>
              Load into cart
            </Button>
          )}
        </div>
      )}
      {b.recent_runs.length > 0 && (
        <p className="text-xs text-muted-foreground">
          History: {b.recent_runs.map((r) => `${r.scheduled_for} ${r.status.toLowerCase().replace(/_/g, " ")}${r.items_total_paise != null ? ` ${formatPrice(r.items_total_paise)}` : ""}`).join(" · ")}
        </p>
      )}
    </div>
  );
}

function Recurring() {
  const list = useLoad(() => listRecurring());
  const addresses = useLoad(() => apiClient.getAddresses());
  const [msg, setMsg] = useState<{ text: string; tone: "error" | "success" } | null>(null);
  const [name, setName] = useState("Basket Monthly Essentials");
  const [day, setDay] = useState("1");
  const [start, setStart] = useState(() => new Date().toISOString().slice(0, 10));
  const [end, setEnd] = useState("");
  const [addressId, setAddressId] = useState("");

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Basket Monthly Essentials</h1>
        <p className="text-sm text-muted-foreground">
          Save your cart as a monthly basket. A day before each date we check current prices, stock, offers and delivery and send you an in-app notice. You review it, load it into your cart and check out yourself — nothing is ordered or charged automatically.
        </p>
      </div>
      {msg && <Notice text={msg.text} tone={msg.tone} />}
      <div className="space-y-2 rounded-xl border bg-white p-4 text-sm">
        <p className="font-semibold">Create from my current cart</p>
        <div className="grid gap-2 sm:grid-cols-2">
          <Input value={name} onChange={(e) => setName(e.target.value)} aria-label="Name" />
          <label className="flex items-center gap-2 text-xs">Day of month (1–28) <Input type="number" min={1} max={28} value={day} onChange={(e) => setDay(e.target.value)} className="w-20" /></label>
          <label className="flex items-center gap-2 text-xs">Start <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} /></label>
          <label className="flex items-center gap-2 text-xs">End (optional) <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} /></label>
          <select value={addressId} onChange={(e) => setAddressId(e.target.value)} className="h-9 rounded-md border bg-background px-2 text-sm" aria-label="Delivery address">
            <option value="">Delivery address (optional)</option>
            {addresses.data?.map((a) => <option key={a.id} value={a.id}>{a.recipient_name} · {a.city} {a.postal_code}</option>)}
          </select>
        </div>
        <Button
          onClick={async () => {
            try {
              await createRecurring({ name, day_of_month: Number(day), start_date: start, end_date: end || null, delivery_address_id: addressId || null });
              setMsg({ text: "Monthly basket saved from your cart.", tone: "success" });
              void list.refresh();
            } catch (e) {
              setMsg({ text: errorText(e), tone: "error" });
            }
          }}
        >
          Save monthly basket
        </Button>
        <p className="text-xs text-muted-foreground">Uses the items currently in your <Link href="/cart" className="underline">cart</Link>.</p>
      </div>
      <Status loading={list.loading && !list.data} error={list.error} />
      {list.data?.map((b) => <BasketCard key={b.id} b={b} onChange={() => void list.refresh()} setMsg={setMsg} />)}
    </div>
  );
}

export default function RecurringPage() {
  return (
    <ProtectedRoute>
      <div className="container mx-auto px-4 py-8 sm:py-12 max-w-6xl">
        <div className="flex flex-col md:flex-row gap-8 items-start">
          <AccountNav />
          <main className="flex-1 w-full space-y-6">
            <Recurring />
          </main>
        </div>
      </div>
    </ProtectedRoute>
  );
}
