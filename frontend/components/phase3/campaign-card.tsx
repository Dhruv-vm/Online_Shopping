"use client";

import Link from "next/link";
import { useState } from "react";
import { joinCampaign, leaveCampaign, shareCampaign, type GroupBuyCampaign } from "@/lib/api/phase3";
import { useI18n } from "@/lib/i18n/i18n-context";
import { formatPrice } from "@/lib/utils";
import { Countdown, errorText, Notice } from "./kit";

export function CampaignCard({ c, onChange }: { c: GroupBuyCampaign; onChange: (c: GroupBuyCampaign) => void }) {
  const { t } = useI18n();
  const [qty, setQty] = useState(1);
  const [err, setErr] = useState<string | null>(null);
  const [share, setShare] = useState<{ whatsapp_url: string; sms_url: string; url: string } | null>(null);
  const pct = Math.min(100, Math.round((c.current_participants / c.min_participants) * 100));
  const joined = c.my_membership?.status === "JOINED";
  const act = async (fn: () => Promise<GroupBuyCampaign>) => {
    setErr(null);
    try {
      onChange(await fn());
    } catch (e) {
      setErr(errorText(e));
    }
  };
  return (
    <div className="rounded-lg border bg-white p-4 shadow-sm">
      <div className="flex justify-between text-xs text-gray-500">
        <span>{c.retailer_name}</span>
        {c.status === "OPEN" ? <span>{t("common.timeLeft")}: <Countdown seconds={c.seconds_remaining} /></span> : <span className="font-semibold">{c.status}</span>}
      </div>
      <Link href={`/community-buying/${c.id}`} className="mt-1 block font-semibold hover:underline">{c.title}</Link>
      <p className="mt-1">
        <span className="font-bold text-emerald-700">{formatPrice(c.group_price_paise)}</span>{" "}
        <span className="text-sm text-gray-400 line-through">{formatPrice(c.list_price_paise)}</span>{" "}
        <span className="text-xs text-emerald-700">-{c.discount_percent}%</span>
      </p>
      <div className="mt-3 h-2 rounded bg-gray-100" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
        <div className="h-2 rounded bg-emerald-500" style={{ width: `${pct}%` }} />
      </div>
      <p className="mt-1 text-xs text-gray-600">
        {c.current_participants}/{c.min_participants} joined
        {c.participants_needed > 0 ? ` · ${t("feature.membersNeeded", { n: c.participants_needed })}` : " · discount unlocked"}
      </p>
      {c.my_membership && <p className="mt-1 text-xs font-medium text-blue-700">Your status: {c.my_membership.status} ({c.my_membership.quantity})</p>}
      {c.status === "OPEN" && (
        <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
          {!joined ? (
            <>
              <input type="number" min={1} max={c.max_quantity_per_member} value={qty} onChange={(e) => setQty(Number(e.target.value))} className="w-16 rounded border px-2 py-1" aria-label="Quantity" />
              <button onClick={() => act(() => joinCampaign(c.id, qty))} className="rounded bg-emerald-600 px-3 py-1 text-white">{t("feature.joinGroup")}</button>
            </>
          ) : (
            <button onClick={() => act(() => leaveCampaign(c.id))} className="rounded border px-3 py-1">Leave</button>
          )}
          <button onClick={async () => { try { setShare(await shareCampaign(c.id)); } catch (e) { setErr(errorText(e)); } }} className="rounded border px-3 py-1">Invite</button>
        </div>
      )}
      {share && (
        <div className="mt-2 flex gap-3 text-xs">
          <a href={share.whatsapp_url} target="_blank" rel="noopener noreferrer" className="text-emerald-700 underline">WhatsApp</a>
          <a href={share.sms_url} className="underline">SMS</a>
          <button onClick={() => navigator.clipboard?.writeText(share.url)} className="underline">Copy link</button>
        </div>
      )}
      {c.status === "SUCCESSFUL" && c.my_membership?.status === "AWARDED" && (
        <Notice tone="success" text="Discount unlocked! Add this item to your basket and check out within 48 hours to pay the group price." />
      )}
      <Notice tone="error" text={err} />
    </div>
  );
}
