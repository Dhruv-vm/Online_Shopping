"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { Bot, Send } from "lucide-react";
import { ProductImage } from "@/components/catalogue/product-image";
import { errorText } from "@/components/phase3/kit";
import { askAssistant, type AssistantOption, type AssistantReply } from "@/lib/api/marketplace";
import { useI18n } from "@/lib/i18n/i18n-context";

type Turn = { role: "user"; text: string } | { role: "assistant"; reply: AssistantReply } | { role: "error"; text: string };

function OptionCard({ o }: { o: AssistantOption }) {
  const { t, money } = useI18n();
  return (
    <div className="flex gap-3 rounded-lg border bg-white p-3">
      <div className="h-16 w-16 shrink-0 overflow-hidden rounded-md bg-surface"><ProductImage src={o.image_url} alt={o.name} /></div>
      <div className="min-w-0 text-sm">
        <p className="line-clamp-2 font-semibold">{o.name}</p>
        <p className="text-xs text-muted-foreground">{o.brand}</p>
        <p className="mt-1">
          <span className="font-bold text-brand-dark">{money(o.best_price_paise)}</span>
          {!o.within_budget && <span className="ml-2 text-xs text-red-700">{t("assistant.overBudget")}</span>}
        </p>
        <p className="mt-1 text-xs text-muted-foreground">{o.explanation}</p>
        <ul className="mt-1 flex flex-wrap gap-1.5 text-[11px]">
          {o.sellers.map((s) => (
            <li key={s.listing_id} className="rounded bg-surface px-1.5 py-0.5">
              {s.retailer_name}: {money(s.price_paise)}
              {s.negotiable && <span className="ml-1 font-semibold text-brand-dark">· {t("assistant.negotiable")}</span>}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export default function AssistantPage() {
  const { t } = useI18n();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);

  const ask = async (msg: string) => {
    if (!msg.trim()) return;
    setTurns((p) => [...p, { role: "user", text: msg }]);
    setText("");
    setBusy(true);
    try {
      const reply = await askAssistant(msg);
      setTurns((p) => [...p, { role: "assistant", reply }]);
    } catch (e) {
      setTurns((p) => [...p, { role: "error", text: errorText(e) }]);
    } finally {
      setBusy(false);
      setTimeout(() => end.current?.scrollIntoView({ behavior: "smooth" }), 50);
    }
  };

  return (
    <div className="container-page max-w-3xl py-8">
      <h1 className="flex items-center gap-2 text-2xl font-bold"><Bot className="h-6 w-6 text-brand" /> {t("nav.assistant")}</h1>
      <p className="mt-1 text-sm text-muted-foreground">{t("assistant.subtitle")}</p>
      <p className="mt-3 rounded-md border border-sky-200 bg-sky-50 p-2 text-xs text-sky-900">{t("assistant.ruleBased")}</p>

      <div className="mt-6 space-y-4">
        {turns.length === 0 && (
          <div className="flex flex-wrap gap-2">
            {["assistant.example1", "assistant.example2", "assistant.example3"].map((k) => (
              <button key={k} type="button" onClick={() => ask(t(k))} className="rounded-full border bg-white px-3 py-1.5 text-sm hover:border-brand">{t(k)}</button>
            ))}
          </div>
        )}
        {turns.map((turn, i) =>
          turn.role === "user" ? (
            <div key={i} className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-sm bg-brand px-4 py-2 text-sm text-white">{turn.text}</div>
          ) : turn.role === "error" ? (
            <div key={i} role="alert" className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">{turn.text}</div>
          ) : (
            <div key={i} className="space-y-3 rounded-2xl rounded-bl-sm border bg-surface p-4">
              <p className="text-sm">{turn.reply.message}</p>
              {turn.reply.options.length > 0 && <div className="grid gap-2">{turn.reply.options.map((o) => <OptionCard key={o.product_id} o={o} />)}</div>}
              {turn.reply.alternatives.length > 0 && (
                <>
                  <p className="text-xs font-semibold uppercase text-muted-foreground">{t("assistant.alternatives")}</p>
                  <div className="grid gap-2">{turn.reply.alternatives.map((o) => <OptionCard key={o.product_id} o={o} />)}</div>
                </>
              )}
              {turn.reply.options.length === 0 && turn.reply.understood.query ? (
                <Link href={`/search?q=${encodeURIComponent(String(turn.reply.understood.query))}`} className="text-sm text-brand underline">{t("assistant.searchInstead")}</Link>
              ) : null}
            </div>
          ),
        )}
        {busy && <p className="text-sm text-muted-foreground">{t("assistant.thinking")}</p>}
        <div ref={end} />
      </div>

      <form onSubmit={(e) => { e.preventDefault(); ask(text); }} className="sticky bottom-4 mt-6 flex gap-2 rounded-xl border bg-white p-2 shadow-sm">
        <label htmlFor="ask" className="sr-only">{t("assistant.placeholder")}</label>
        <input id="ask" value={text} onChange={(e) => setText(e.target.value)} placeholder={t("assistant.placeholder")} maxLength={500} className="h-10 flex-1 rounded-md px-2 text-sm focus:outline-none" />
        <button type="submit" disabled={busy || !text.trim()} className="inline-flex h-10 items-center gap-1.5 rounded-md bg-brand px-4 text-sm font-semibold text-white disabled:opacity-50">
          <Send className="h-4 w-4" /> {t("assistant.ask")}
        </button>
      </form>
    </div>
  );
}
