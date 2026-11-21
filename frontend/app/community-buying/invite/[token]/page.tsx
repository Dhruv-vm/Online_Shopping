"use client";

import { use, useState } from "react";
import Link from "next/link";
import { joinViaInvite, previewInvite } from "@/lib/api/phase3";
import { useAuth } from "@/lib/auth/auth-context";
import { formatPrice } from "@/lib/utils";
import { errorText, Notice, PageTitle, Status, useLoad } from "@/components/phase3/kit";

export default function GroupBuyInvitePage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params);
  const { isAuthenticated } = useAuth();
  const invite = useLoad(() => previewInvite(token), [token]);
  const [qty, setQty] = useState(1);
  const [msg, setMsg] = useState<{ text: string; tone: "error" | "success" } | null>(null);
  const [joinedId, setJoinedId] = useState<string | null>(null);
  const v = invite.data;

  return (
    <div className="container mx-auto max-w-xl space-y-4 px-4 py-8">
      <PageTitle title="Group buy invitation" subtitle="Join with others to unlock a lower price. No payment is taken now." />
      <Status loading={invite.loading} error={invite.error} />
      {msg && <Notice text={msg.text} tone={msg.tone} />}
      {v && (
        <div className="space-y-2 rounded border bg-white p-4 text-sm">
          <p className="text-base font-semibold">{v.title}</p>
          <p className="text-muted-foreground">{v.product_name}</p>
          <p>
            Group price <strong>{formatPrice(v.group_price_paise)}</strong>{" "}
            <span className="text-muted-foreground line-through">{formatPrice(v.list_price_paise)}</span>{" "}
            ({v.discount_bps / 100}% off)
          </p>
          <p>{v.current_participants} of {v.min_participants} joined (max {v.max_participants})</p>
          <p className="text-xs text-muted-foreground">
            Group buy ends {new Date(v.campaign_expires_at).toLocaleString()} · this invite is valid until {new Date(v.invite_expires_at).toLocaleString()}
          </p>
          {!v.can_join && <p className="text-amber-700">{v.reason}</p>}
          {v.can_join && !joinedId && (
            isAuthenticated ? (
              <div className="flex items-center gap-2">
                <input type="number" min={1} value={qty} onChange={(e) => setQty(Math.max(1, Number(e.target.value) || 1))} className="w-20 rounded border px-2 py-1" aria-label="Quantity" />
                <button
                  type="button"
                  className="rounded bg-brand px-3 py-1.5 text-white"
                  onClick={async () => {
                    try {
                      const c = await joinViaInvite(token, qty);
                      setJoinedId(c.id);
                      setMsg({ text: "You joined the group buy.", tone: "success" });
                      await invite.refresh();
                    } catch (e) {
                      setMsg({ text: errorText(e), tone: "error" });
                    }
                  }}
                >
                  Join group buy
                </button>
              </div>
            ) : (
              <Link href={`/login?redirect=${encodeURIComponent(`/community-buying/invite/${token}`)}`} className="inline-block rounded bg-brand px-3 py-1.5 text-white">
                Sign in to join
              </Link>
            )
          )}
          {joinedId && <Link href={`/community-buying/${joinedId}`} className="underline">Open the group buy</Link>}
        </div>
      )}
    </div>
  );
}
