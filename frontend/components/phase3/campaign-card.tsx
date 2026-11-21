"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ProductImage } from "@/components/catalogue/product-image";
import { joinCampaign, leaveCampaign, shareCampaign, type GroupBuyCampaign } from "@/lib/api/phase3";
import { useAuth } from "@/lib/auth/auth-context";
import { useCart } from "@/lib/cart/cart-context";
import { useI18n } from "@/lib/i18n/i18n-context";
import { Countdown, errorText, Notice } from "./kit";

export function CampaignCard({ c, onChange }: { c: GroupBuyCampaign; onChange: (c: GroupBuyCampaign) => void }) {
  const { t, money } = useI18n();
  const { user } = useAuth();
  const { addItem } = useCart();
  const router = useRouter();
  const [qty, setQty] = useState(1);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [share, setShare] = useState<{ whatsapp_url: string; sms_url: string; url: string } | null>(null);
  const pct = Math.min(100, Math.round((c.current_participants / Math.max(1, c.min_participants)) * 100));
  const joined = c.my_membership?.status === "JOINED";
  const awarded = c.my_membership?.status === "AWARDED";

  const act = async (fn: () => Promise<GroupBuyCampaign>) => {
    setErr(null);
    setBusy(true);
    try {
      onChange(await fn());
    } catch (e) {
      setErr(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const checkout = async () => {
    setBusy(true);
    try {
      await addItem(c.listing_id, c.my_membership?.quantity ?? 1);
      router.push("/cart");
    } catch (e) {
      setErr(errorText(e));
      setBusy(false);
    }
  };

  return (
    <article className="flex flex-col overflow-hidden rounded-xl border bg-white shadow-sm">
      <Link href={`/community-buying/${c.id}`} className="block aspect-[4/3] bg-surface">
        <ProductImage src={c.image_url} alt={c.product_name} />
      </Link>
      <div className="flex flex-1 flex-col p-4">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span className="truncate">{c.retailer_name}</span>
          {c.status === "OPEN" ? (
            <span>{t("common.timeLeft")}: <Countdown seconds={c.seconds_remaining} /></span>
          ) : (
            <span className="font-semibold">{t(`groupStatus.${c.status}`)}</span>
          )}
        </div>
        <Link href={`/community-buying/${c.id}`} className="mt-1 line-clamp-2 font-semibold hover:text-brand">{c.title}</Link>
        {c.started_by_customer && <span className="mt-1 w-fit rounded bg-brand-light px-1.5 text-[11px] text-brand-dark">{t("group.startedByCustomer")}</span>}
        <p className="mt-2">
          <span className="text-lg font-bold text-brand-dark">{money(c.group_price_paise)}</span>{" "}
          <span className="text-sm text-muted-foreground line-through">{money(c.list_price_paise)}</span>{" "}
          <span className="text-xs font-semibold text-brand">−{c.discount_percent}%</span>
        </p>
        <div className="mt-3 h-2 rounded-full bg-muted" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label={t("group.progress")}>
          <div className="h-2 rounded-full bg-brand" style={{ width: `${pct}%` }} />
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          {t("group.joinedOf", { n: c.current_participants, min: c.min_participants, max: c.max_participants })}
          {" · "}
          {c.participants_needed > 0 ? t("feature.membersNeeded", { n: c.participants_needed }) : t("group.unlocked")}
        </p>
        {c.participant_initials && c.participant_initials.length > 0 && (
          <div className="mt-2 flex -space-x-1.5" aria-label={t("group.members")}>
            {c.participant_initials.slice(0, 8).map((i, idx) => (
              <span key={idx} className="flex h-6 w-6 items-center justify-center rounded-full border-2 border-white bg-brand-light text-[10px] font-bold text-brand-dark">{i}</span>
            ))}
            {c.participant_initials.length > 8 && <span className="pl-3 text-xs text-muted-foreground">+{c.participant_initials.length - 8}</span>}
          </div>
        )}
        {c.my_membership && (
          <p className="mt-2 text-xs font-medium text-brand-dark">{t("group.yourStatus", { status: t(`memberStatus.${c.my_membership.status}`), qty: c.my_membership.quantity })}</p>
        )}

        <div className="mt-auto pt-3">
          {c.status === "OPEN" && (!user || user.role === "customer") && (
            <div className="flex flex-wrap items-center gap-2 text-sm">
              {!user ? (
                <Link href={`/login?redirect=/community-buying/${c.id}`} className="rounded-lg bg-brand px-3 py-1.5 font-semibold text-white">{t("group.signInToJoin")}</Link>
              ) : !joined ? (
                <>
                  <label className="sr-only" htmlFor={`qty-${c.id}`}>{t("common.quantity")}</label>
                  <input id={`qty-${c.id}`} type="number" min={1} max={c.max_quantity_per_member} value={qty} onChange={(e) => setQty(Math.max(1, Math.min(c.max_quantity_per_member, Number(e.target.value) || 1)))} className="h-9 w-16 rounded-md border px-2" />
                  <button type="button" disabled={busy} onClick={() => act(() => joinCampaign(c.id, qty))} className="rounded-lg bg-brand px-3 py-1.5 font-semibold text-white disabled:opacity-60">{t("feature.joinGroup")}</button>
                </>
              ) : (
                <button type="button" disabled={busy} onClick={() => act(() => leaveCampaign(c.id))} className="rounded-lg border px-3 py-1.5">{t("group.leave")}</button>
              )}
              {user && (
                <button type="button" onClick={async () => { try { setShare(await shareCampaign(c.id)); } catch (e) { setErr(errorText(e)); } }} className="rounded-lg border px-3 py-1.5">{t("group.invite")}</button>
              )}
            </div>
          )}
          {share && (
            <div className="mt-2 flex gap-3 text-xs">
              <a href={share.whatsapp_url} target="_blank" rel="noopener noreferrer" className="text-brand underline">WhatsApp</a>
              <a href={share.sms_url} className="underline">SMS</a>
              <button type="button" onClick={() => navigator.clipboard?.writeText(share.url)} className="underline">{t("group.copyLink")}</button>
            </div>
          )}
          {c.status === "SUCCESSFUL" && awarded && (
            <div className="mt-2 space-y-2">
              <Notice tone="success" text={t("group.awardedNotice")} />
              <button type="button" disabled={busy} onClick={checkout} className="w-full rounded-lg bg-brand py-2 text-sm font-semibold text-white disabled:opacity-60">{t("group.checkoutNow")}</button>
            </div>
          )}
          <Notice tone="error" text={err} />
        </div>
      </div>
    </article>
  );
}
