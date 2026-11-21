"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { formatPrice } from "@/lib/utils";
import { ApiClientError } from "@/lib/api/client";
import {
  createIntentBasket, getIntent, listIntents, submitIntent, updateIntent,
  type IntentItemIn, type IntentSummary, type IntentWorkflow,
} from "@/lib/api/intent-workflow";

const FREQUENCIES = ["ONCE", "WEEKLY", "BIWEEKLY", "MONTHLY", "QUARTERLY"];
const STATUS_TEXT: Record<string, string> = {
  MATCHED: "Everything is available near you",
  PARTIALLY_MATCHED: "Some items are available; the rest are recorded as demand",
  WAITING_FOR_SUPPLY: "Not available near you yet — recorded as demand",
};
const blankItem = (): IntentItemIn => ({ name: "", quantity: 1, specs: "" });

function errText(e: unknown) {
  return e instanceof ApiClientError ? e.message : "Something went wrong. Please try again.";
}

export function IntentWorkflowCard() {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [items, setItems] = useState<IntentItemIn[]>([blankItem()]);
  const [budget, setBudget] = useState("");
  const [frequency, setFrequency] = useState("ONCE");
  const [pincode, setPincode] = useState("");
  const [purchaseBy, setPurchaseBy] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<IntentWorkflow | null>(null);
  const [basketMsg, setBasketMsg] = useState<string | null>(null);
  const [saved, setSaved] = useState<IntentSummary[]>([]);

  const loadSaved = useCallback(async () => {
    try {
      setSaved(await listIntents());
    } catch {
      /* list is optional */
    }
  }, []);
  useEffect(() => {
    void loadSaved();
  }, [loadSaved]);

  const fillForm = (w: IntentWorkflow) => {
    setEditingId(w.intention.id);
    setTitle(w.intention.title);
    setItems(w.items_requested.map((i) => ({ name: i.name, quantity: i.quantity, specs: i.specs ?? "" })));
    setBudget(w.intention.budget_paise != null ? String(w.intention.budget_paise / 100) : "");
    setFrequency(w.intention.frequency);
    setPincode(w.pincode ?? "");
    setPurchaseBy(w.purchase_by ?? "");
  };

  const submit = async () => {
    setError(null);
    setBasketMsg(null);
    const clean = items.filter((i) => i.name.trim()).map((i) => ({ name: i.name.trim(), quantity: Math.max(1, Number(i.quantity) || 1), specs: i.specs?.trim() || null }));
    if (!title.trim() || clean.length === 0) {
      setError("Give your intent a name and at least one item.");
      return;
    }
    const body = {
      title: title.trim(),
      items: clean,
      budget_paise: budget ? Math.round(Number(budget) * 100) : null,
      frequency,
      pincode: pincode.trim() || null,
      purchase_by: purchaseBy || null,
    };
    setBusy(true);
    try {
      const w = editingId ? await updateIntent(editingId, body) : await submitIntent(body);
      setResult(w);
      setEditingId(w.intention.id);
      void loadSaved();
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  };

  const open = async (id: string) => {
    setError(null);
    setBasketMsg(null);
    setBusy(true);
    try {
      const w = await getIntent(id);
      setResult(w);
      fillForm(w);
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  };

  const basket = async () => {
    if (!result) return;
    setBusy(true);
    try {
      const r = await createIntentBasket(result.intention.id);
      setBasketMsg(r.message);
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  };

  const reset = () => {
    setEditingId(null);
    setTitle("");
    setItems([blankItem()]);
    setBudget("");
    setFrequency("ONCE");
    setPincode("");
    setPurchaseBy("");
    setResult(null);
    setError(null);
    setBasketMsg(null);
  };

  return (
    <Card className="border shadow-xs">
      <CardHeader className="pb-4 border-b">
        <CardTitle className="text-base font-semibold">Tell Basket what you want to buy</CardTitle>
        <p className="text-xs text-muted-foreground">
          We save it, show what we understood, match it to real listings from stores that deliver to your PIN, and record anything unavailable as demand stores can see.
        </p>
      </CardHeader>
      <CardContent className="space-y-4 pt-4 text-sm">
        <div className="grid gap-2 sm:grid-cols-2">
          <Input placeholder="Name, e.g. Monthly groceries" value={title} onChange={(e) => setTitle(e.target.value)} aria-label="Intent name" />
          <Input placeholder="Delivery PIN code" value={pincode} onChange={(e) => setPincode(e.target.value)} inputMode="numeric" maxLength={6} aria-label="Delivery PIN code" />
          <Input placeholder="Budget ₹ (optional)" value={budget} onChange={(e) => setBudget(e.target.value)} inputMode="decimal" aria-label="Budget in rupees" />
          <div className="flex gap-2">
            <select value={frequency} onChange={(e) => setFrequency(e.target.value)} className="h-9 flex-1 rounded-md border bg-background px-2 text-sm" aria-label="How often">
              {FREQUENCIES.map((f) => <option key={f} value={f}>{f === "ONCE" ? "One time" : f.charAt(0) + f.slice(1).toLowerCase()}</option>)}
            </select>
            <Input type="date" value={purchaseBy} onChange={(e) => setPurchaseBy(e.target.value)} aria-label="Buy by (optional)" className="flex-1" />
          </div>
        </div>
        <div className="space-y-2">
          {items.map((it, i) => (
            <div key={i} className="flex gap-2">
              <Input placeholder="Item, e.g. Basmati rice" value={it.name} onChange={(e) => setItems(items.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))} aria-label={`Item ${i + 1}`} />
              <Input type="number" min={1} value={it.quantity} onChange={(e) => setItems(items.map((x, j) => (j === i ? { ...x, quantity: Number(e.target.value) } : x)))} className="w-20" aria-label={`Quantity for item ${i + 1}`} />
              <Input placeholder="Specs (optional)" value={it.specs ?? ""} onChange={(e) => setItems(items.map((x, j) => (j === i ? { ...x, specs: e.target.value } : x)))} aria-label={`Specifications for item ${i + 1}`} />
              {items.length > 1 && <Button type="button" variant="ghost" size="sm" onClick={() => setItems(items.filter((_, j) => j !== i))}>Remove</Button>}
            </div>
          ))}
          <Button type="button" variant="outline" size="sm" onClick={() => setItems([...items, blankItem()])} disabled={items.length >= 20}>Add item</Button>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="button" onClick={submit} disabled={busy}>{editingId ? "Update intent" : "Save intent"}</Button>
          {editingId && <Button type="button" variant="ghost" onClick={reset}>New intent</Button>}
        </div>
        {error && <p role="alert" className="text-sm text-red-600">{error}</p>}

        {result && (
          <div className="space-y-3 rounded-lg border p-3" aria-live="polite">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline">{result.updated_existing ? "Intent updated" : "Intent saved"}</Badge>
              <span className="font-semibold">{STATUS_TEXT[result.status]}</span>
            </div>
            <p className="text-xs text-muted-foreground">
              Understood: {result.items.map((i) => `${i.quantity}× ${i.understood_as}`).join(", ")}
              {result.intention.budget_paise != null && ` · budget ${formatPrice(result.intention.budget_paise)}`}
              {` · ${result.intention.frequency === "ONCE" ? "one time" : result.intention.frequency.toLowerCase()}`}
              {result.pincode && ` · PIN ${result.pincode}`}
              {result.purchase_by && ` · buy by ${result.purchase_by}`}
            </p>
            {result.items.map((it) => (
              <div key={it.name} className="rounded border p-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium">{it.quantity}× {it.understood_as}</span>
                  <span className={it.status === "AVAILABLE" ? "text-xs text-emerald-700" : "text-xs text-amber-700"}>
                    {it.status === "AVAILABLE" ? `${it.retailer_count} store(s) can supply` : "Not available near you"}
                    {it.category ? ` · ${it.category}` : ""}
                  </span>
                </div>
                {it.matches.length > 0 && (
                  <ul className="mt-1 space-y-0.5 text-xs">
                    {it.matches.map((m) => (
                      <li key={m.listing_id}>
                        <Link href={`/products/${m.product_slug}`} className="underline">{m.product_name}{m.variant_name ? ` (${m.variant_name})` : ""}</Link>
                        {` · ${m.retailer_name} · ${formatPrice(m.price_paise)}`}
                        {m.original_price_paise > m.price_paise && <span className="text-muted-foreground line-through"> {formatPrice(m.original_price_paise)}</span>}
                        {m.offers.length > 0 && <span className="text-emerald-700"> · {m.offers.join(", ")}</span>}
                      </li>
                    ))}
                  </ul>
                )}
                {it.demand && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    Demand Gap “{it.demand.display_name}”: {it.demand.unique_customers} shopper(s) · {it.demand.visible_to_retailers ? "visible to stores" : `stores see it at ${it.demand.visibility_threshold}`}
                    {it.demand.signal_recorded_now ? " · your request was added" : " · your request was already counted"}
                  </p>
                )}
                <p className="mt-1 text-xs">{it.next_step}</p>
              </div>
            ))}
            {result.can_create_basket && (
              <p className="text-xs">
                Cheapest matching basket: <strong>{formatPrice(result.cheapest_total_paise)}</strong>
                {result.within_budget === true && <span className="text-emerald-700"> · within budget</span>}
                {result.within_budget === false && <span className="text-red-600"> · above budget</span>}
              </p>
            )}
            {result.next_steps.length > 0 && (
              <ul className="list-disc pl-5 text-xs text-muted-foreground">
                {result.next_steps.map((s) => <li key={s}>{s}</li>)}
              </ul>
            )}
            <div className="flex flex-wrap gap-2">
              {result.can_create_basket && <Button type="button" size="sm" onClick={basket} disabled={busy}>Create basket</Button>}
              <Button type="button" size="sm" variant="outline" onClick={() => open(result.intention.id)} disabled={busy}>Refresh status</Button>
            </div>
            {basketMsg && <p className="text-xs text-emerald-700">{basketMsg} <Link href="/cart" className="underline">Go to cart</Link></p>}
          </div>
        )}

        {saved.length > 0 && (
          <div className="space-y-1">
            <p className="text-xs font-semibold">Your intents</p>
            {saved.map((s) => (
              <div key={s.id} className="flex items-center justify-between rounded border px-2 py-1 text-xs">
                <span>{s.title} · {s.item_count} item(s){s.pincode ? ` · PIN ${s.pincode}` : ""}{s.last_status ? ` · ${STATUS_TEXT[s.last_status] ?? s.last_status}` : ""}</span>
                <Button type="button" size="sm" variant="ghost" onClick={() => open(s.id)}>Review</Button>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
