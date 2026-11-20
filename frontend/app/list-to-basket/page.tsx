"use client";

import Link from "next/link";
import { useState } from "react";
import { buildCartFromList, parseShoppingList, type ParsedListItem } from "@/lib/api/phase3";
import { useCart } from "@/lib/cart/cart-context";
import { useI18n } from "@/lib/i18n/i18n-context";
import { formatPrice } from "@/lib/utils";
import { errorText, Notice, PageTitle } from "@/components/phase3/kit";

type Row = ParsedListItem & { chosen: string | null; qty: number };

export default function ListToBasketPage() {
  const { t } = useI18n();
  const { refreshCart } = useCart();
  const [text, setText] = useState("");
  const [rows, setRows] = useState<Row[] | null>(null);
  const [msg, setMsg] = useState<{ text: string; tone: "error" | "success" | "info" } | null>(null);

  const parse = async (body: Parameters<typeof parseShoppingList>[0]) => {
    setMsg(null);
    try {
      const res = await parseShoppingList(body);
      setText(res.raw_text);
      setRows(res.items.map((i) => ({ ...i, chosen: i.suggested_listing_id, qty: i.quantity })));
    } catch (e) {
      setMsg({ text: errorText(e), tone: "error" });
    }
  };

  const onPhoto = async (file: File | undefined) => {
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) return setMsg({ text: "Image must be 5 MB or smaller.", tone: "error" });
    const type = file.type as "image/jpeg" | "image/png" | "image/webp";
    if (!["image/jpeg", "image/png", "image/webp"].includes(type)) return setMsg({ text: "Use a JPEG, PNG or WebP photo.", tone: "error" });
    const b64 = await new Promise<string>((resolve, reject) => {
      const r = new FileReader();
      r.onload = () => resolve(String(r.result).split(",")[1] ?? "");
      r.onerror = reject;
      r.readAsDataURL(file);
    });
    await parse({ image_base64: b64, content_type: type });
  };

  return (
    <div className="container mx-auto max-w-3xl px-4 py-8">
      <PageTitle title={t("nav.listToBasket")} subtitle="Upload a photo of your shopping list or type it. Review the matches before anything is added." />
      <div className="space-y-3 rounded-lg border bg-white p-4">
        <label className="block text-sm">
          Photo of list
          <input type="file" accept="image/jpeg,image/png,image/webp" capture="environment" onChange={(e) => onPhoto(e.target.files?.[0])} className="mt-1 block text-sm" />
        </label>
        <textarea value={text} onChange={(e) => setText(e.target.value)} rows={5} placeholder={"1kg Aashirvaad atta\n500g Amul butter\nDettol soap 3pc"} className="w-full rounded border p-2 text-sm" aria-label="Shopping list text" />
        <button disabled={text.trim().length < 2} onClick={() => parse({ text })} className="rounded bg-emerald-600 px-4 py-1 text-sm text-white disabled:opacity-40">Find products</button>
        {msg && <Notice text={msg.text} tone={msg.tone} />}
      </div>
      {rows && (
        <div className="mt-6">
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-gray-500"><th>Your list</th><th>Match</th><th>Qty</th></tr></thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} className="border-t align-top">
                  <td className="py-2">{r.line}<div className="text-xs text-gray-400">→ {r.interpreted_as}</div></td>
                  <td className="py-2">
                    {r.candidates.length === 0 ? <span className="text-xs text-gray-500">{t("feature.noResults")}</span> : (
                      <select value={r.chosen ?? ""} onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, chosen: e.target.value || null } : x)))} className="w-full rounded border px-1 py-1 text-xs" aria-label={`Match for ${r.name}`}>
                        <option value="">Skip</option>
                        {r.candidates.map((c) => <option key={c.listing_id} value={c.listing_id}>{c.product_name} · {c.retailer_name} · {formatPrice(c.price_paise)}</option>)}
                      </select>
                    )}
                  </td>
                  <td className="py-2"><input type="number" min={1} max={10} value={r.qty} onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, qty: Number(e.target.value) } : x)))} className="w-16 rounded border px-1" aria-label={`Quantity for ${r.name}`} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <button
            onClick={async () => {
              const items = rows.filter((r) => r.chosen).map((r) => ({ listing_id: r.chosen!, quantity: r.qty }));
              if (!items.length) return setMsg({ text: "Choose at least one product.", tone: "error" });
              try {
                const res = await buildCartFromList(items);
                await refreshCart();
                setMsg({ text: `${res.added} item(s) added${res.skipped.length ? `, ${res.skipped.length} skipped` : ""}.`, tone: "success" });
              } catch (e) {
                setMsg({ text: errorText(e), tone: "error" });
              }
            }}
            className="mt-4 rounded bg-emerald-600 px-4 py-2 text-sm text-white"
          >
            {t("common.addToBasket")}
          </button>{" "}
          <Link href="/cart" className="text-sm underline">{t("nav.cart")}</Link>
        </div>
      )}
    </div>
  );
}
