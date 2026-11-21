"use client";

import { useState } from "react";
import { acceptNegotiation, counterOffer, startNegotiation, type NegotiationSession } from "@/lib/api/phase3";
import { useI18n } from "@/lib/i18n/i18n-context";
import { formatPrice } from "@/lib/utils";
import { errorText, Notice, rupeesToPaise } from "./kit";

/** AI Negotiator (Phase 3D) chat panel for the cart. Accepting returns a checkout quote id. */
export function NegotiatorPanel({ onQuote }: { onQuote?: (quoteId: string) => void }) {
  const { t, lang } = useI18n();
  const [s, setS] = useState<NegotiationSession | null>(null);
  const [offer, setOffer] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const run = async (fn: () => Promise<NegotiationSession>) => {
    setErr(null);
    try {
      const r = await fn();
      setS(r);
      if (r.quote_id) onQuote?.(r.quote_id);
    } catch (e) {
      setErr(errorText(e));
    }
  };
  return (
    <div className="rounded-card border bg-white p-4 shadow-card">
      <h3 className="text-sm font-semibold">{t("feature.negotiate")}</h3>
      {!s ? (
        <button onClick={() => run(() => startNegotiation({ language: lang }))} className="press mt-2 rounded-full bg-ink px-4 py-1.5 text-sm font-semibold text-white hover:bg-charcoal">
          {t("feature.negotiate")}
        </button>
      ) : (
        <>
          <ul className="mt-2 max-h-48 space-y-1 overflow-y-auto text-sm" aria-live="polite">
            {s.messages.map((m, i) => (
              <li key={i} className={m.role === "assistant" ? "rounded-xl bg-cream p-2" : "rounded bg-gray-100 p-2 text-right"}>{m.text}</li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-gray-500">Offer {formatPrice(s.current_offer_paise)} · round {s.current_round}/{s.max_rounds} · {s.status}</p>
          {s.status === "IN_PROGRESS" && (
            <div className="mt-2 flex gap-2">
              <input type="number" min={1} value={offer} onChange={(e) => setOffer(e.target.value)} placeholder="Your price ₹" className="w-28 rounded border px-2 py-1 text-sm" aria-label="Your price" />
              <button disabled={!offer} onClick={() => run(() => counterOffer(s.id, rupeesToPaise(offer)))} className="press rounded-full border px-3 py-1 text-sm disabled:opacity-40 hover:border-ink/40">Counter</button>
              <button onClick={() => run(() => acceptNegotiation(s.id))} className="press rounded-full bg-brand-yellow px-3 py-1 text-sm font-semibold text-ink hover:bg-brand-yellow-dark">Accept {formatPrice(s.current_offer_paise)}</button>
            </div>
          )}
          {s.status === "ACCEPTED" && s.quote_total_payable_paise != null && (
            <Notice tone="success" text={`Locked in. Quote total ${formatPrice(s.quote_total_payable_paise)} — continue to reserve & checkout.`} />
          )}
        </>
      )}
      <Notice tone="error" text={err} />
    </div>
  );
}
