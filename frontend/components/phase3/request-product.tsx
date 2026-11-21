"use client";

import { useState } from "react";
import { logDemandSignal } from "@/lib/api/phase3";
import { useI18n } from "@/lib/i18n/i18n-context";
import { errorText } from "./kit";

/** Demand Gap (Phase 3A): "Request this product / Notify me" for zero results or out-of-stock items. */
export function RequestProductButton({ query, listingId, outOfStock }: { query?: string; listingId?: string; outOfStock?: boolean }) {
  const { t } = useI18n();
  const [pincode, setPincode] = useState("");
  const [state, setState] = useState<{ ok: boolean; text: string } | null>(null);
  return (
    <form
      className="mt-4 flex flex-wrap items-center justify-center gap-2 text-sm"
      onSubmit={async (e) => {
        e.preventDefault();
        try {
          const r = await logDemandSignal({
            query_text: query || undefined,
            listing_id: listingId,
            pincode: pincode || undefined,
            signal_type: outOfStock ? "OUT_OF_STOCK" : "WISHLIST",
          });
          setState({ ok: true, text: `Request recorded — ${r.pool.unique_users_count} shopper(s) want this. Local shops will be told.` });
        } catch (err) {
          setState({ ok: false, text: errorText(err) });
        }
      }}
    >
      <input value={pincode} onChange={(e) => setPincode(e.target.value)} pattern="[1-9][0-9]{5}" placeholder="PIN code (optional)" className="w-36 rounded border px-2 py-1" aria-label="PIN code" />
      <button className="rounded bg-amber-500 px-3 py-1 text-white">{outOfStock ? t("feature.notifyMe") : t("feature.requestProduct")}</button>
      {state && <p role="status" className={`w-full text-center text-xs ${state.ok ? "text-emerald-700" : "text-red-600"}`}>{state.text}</p>}
    </form>
  );
}
