"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { getSaleStream, type SaleStreamEventType, type SaleStreamItem } from "@/lib/api/phase3";
import { useCart } from "@/lib/cart/cart-context";
import { useI18n } from "@/lib/i18n/i18n-context";
import { formatPrice } from "@/lib/utils";
import { Countdown, errorText, Notice, PageTitle, Status } from "@/components/phase3/kit";

const TYPES: (SaleStreamEventType | "")[] = ["", "FLASH_DEAL", "PRICE_DROP", "HOT_SELLER"];

export default function SaleStreamPage() {
  const { t } = useI18n();
  const { addItem } = useCart();
  const [type, setType] = useState<SaleStreamEventType | "">("");
  const [items, setItems] = useState<SaleStreamItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const serverTime = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    serverTime.current = null;
    setItems([]);
    setLoading(true);
    const poll = async () => {
      try {
        const res = await getSaleStream({ event_type: type || undefined, since: serverTime.current ?? undefined, limit: 30 });
        if (cancelled) return;
        serverTime.current = res.server_time;
        setItems((prev) => {
          const seen = new Set(prev.map((p) => p.id));
          return [...res.items.filter((i) => !seen.has(i.id)), ...prev].filter((i) => new Date(i.expires_at) > new Date());
        });
        setError(null);
        timer = setTimeout(poll, res.poll_after_seconds * 1000);
      } catch (e) {
        if (!cancelled) setError(errorText(e));
        timer = setTimeout(poll, 30000);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [type]);

  return (
    <div className="container mx-auto max-w-3xl px-4 py-8">
      <PageTitle title={t("nav.saleStream")} subtitle="Live price drops, flash deals and hot sellers from nearby shops." />
      <div className="mb-4 flex flex-wrap gap-2">
        {TYPES.map((k) => (
          <button key={k || "all"} onClick={() => setType(k)} className={`rounded-full border px-3 py-1 text-xs ${type === k ? "border-ink bg-ink text-white" : "bg-white hover:border-ink/40"}`}>
            {k ? k.replace("_", " ") : "All"}
          </button>
        ))}
      </div>
      <Status loading={loading} error={error} />
      <Notice text={msg} tone="success" />
      {!loading && items.length === 0 && <p className="text-sm text-gray-500">No live deals right now. This feed refreshes automatically.</p>}
      <ul className="space-y-3">
        {items.map((i) => (
          <li key={i.id} className="flex gap-4 rounded-lg border bg-white p-4 shadow-sm">
            {i.image_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={i.image_url} alt={i.product_name} className="h-20 w-20 rounded object-cover" />
            ) : (
              <div className="h-20 w-20 rounded bg-gray-100" />
            )}
            <div className="flex-1">
              <div className="flex items-center justify-between text-xs">
                <span className="rounded bg-amber-100 px-2 py-0.5 font-semibold text-amber-800">{i.event_type.replace("_", " ")}</span>
                <span className="text-gray-500">
                  {t("common.timeLeft")}: <Countdown seconds={i.seconds_remaining} />
                </span>
              </div>
              <Link href={`/products/${i.product_id}`} className="mt-1 block font-medium hover:underline">{i.product_name}</Link>
              <p className="text-xs text-gray-500">{i.retailer_name}</p>
              <p className="mt-1">
                <span className="font-bold text-emerald-700">{formatPrice(i.deal_price_paise)}</span>{" "}
                <span className="text-sm text-gray-400 line-through">{formatPrice(i.old_price_paise)}</span>{" "}
                <span className="text-xs text-emerald-700">-{i.discount_pct}%</span>
              </p>
              <div className="mt-2 flex items-center justify-between text-xs">
                <span className={i.stock_remaining <= 5 ? "font-semibold text-red-600" : "text-gray-500"}>
                  {i.stock_remaining > 0 ? t("common.onlyLeft", { n: i.stock_remaining }) : t("common.outOfStock")}
                  {i.units_sold_24h ? ` · ${i.units_sold_24h} sold today` : ""}
                </span>
                <button
                  disabled={i.stock_remaining === 0}
                  onClick={async () => {
                    try {
                      await addItem(i.listing_id, 1);
                      setMsg(`${i.product_name} added to basket`);
                    } catch (e) {
                      setError(errorText(e));
                    }
                  }}
                  className="press rounded-full bg-brand-yellow px-3.5 py-1 font-semibold text-ink hover:bg-brand-yellow-dark disabled:opacity-40"
                >
                  {t("common.addToBasket")}
                </button>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
