"use client";

import { useState } from "react";
import Link from "next/link";
import { ProductImage } from "@/components/catalogue/product-image";
import { CampaignCard } from "@/components/phase3/campaign-card";
import { errorText, Notice, PageTitle, Status, useLoad } from "@/components/phase3/kit";
import { EmptyState } from "@/components/portal/kpi";
import { listGroupBuyTemplates, startGroupBuy } from "@/lib/api/marketplace";
import { listCampaigns } from "@/lib/api/phase3";
import { useAuth } from "@/lib/auth/auth-context";
import { useI18n } from "@/lib/i18n/i18n-context";

export default function CommunityBuyingPage() {
  const { t, money } = useI18n();
  const { user } = useAuth();
  const camps = useLoad(() => listCampaigns({ limit: 50 }));
  const templates = useLoad(() => listGroupBuyTemplates());
  const [msg, setMsg] = useState<{ text: string; tone: "error" | "success" } | null>(null);

  return (
    <div className="container-page py-8">
      <PageTitle title={t("nav.communityBuying")} subtitle={t("group.customerSubtitle")} />
      <ol className="mb-8 grid gap-3 sm:grid-cols-3">
        {["group.how1", "group.how2", "group.how3"].map((k, i) => (
          <li key={k} className="flex items-start gap-3 rounded-xl border bg-white p-4 text-sm">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand text-xs font-bold text-white">{i + 1}</span>
            {t(k)}
          </li>
        ))}
      </ol>

      <h2 className="mb-3 text-lg font-semibold">{t("group.openGroups")}</h2>
      <Status loading={camps.loading} error={camps.error} onRetry={camps.reload} />
      {camps.data && camps.data.items.length === 0 && <EmptyState title={t("group.noOpen")} body={t("group.noOpenBody")} />}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {camps.data?.items.map((c) => (
          <CampaignCard key={c.id} c={c} onChange={(n) => camps.setData({ ...camps.data!, items: camps.data!.items.map((x) => (x.id === n.id ? n : x)) })} />
        ))}
      </div>

      <h2 className="mb-1 mt-10 text-lg font-semibold">{t("group.startOwn")}</h2>
      <p className="mb-3 text-sm text-muted-foreground">{t("group.startOwnBody")}</p>
      {msg && <Notice text={msg.text} tone={msg.tone} />}
      <Status loading={templates.loading} error={templates.error} onRetry={templates.reload} />
      {templates.data && templates.data.items.length === 0 && <EmptyState title={t("group.noTemplates")} />}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {templates.data?.items.map((x) => (
          <article key={x.id} className="overflow-hidden rounded-xl border bg-white">
            <div className="aspect-[4/3] bg-surface"><ProductImage src={x.image_url} alt={x.product_name} /></div>
            <div className="space-y-1.5 p-4 text-sm">
              <p className="line-clamp-2 font-semibold">{x.product_name}</p>
              <p className="text-xs text-muted-foreground">{x.retailer_name}</p>
              <p>
                <span className="font-bold text-brand-dark">{money(x.group_price_paise)}</span>{" "}
                <span className="text-xs text-muted-foreground line-through">{money(x.list_price_paise)}</span>
              </p>
              <p className="text-xs text-muted-foreground">{t("group.templateTerms", { min: x.min_participants, hours: x.duration_hours })}</p>
              {!user ? (
                <Link href="/login?redirect=/community-buying" className="mt-2 block rounded-lg bg-brand py-2 text-center font-semibold text-white">{t("group.signInToStart")}</Link>
              ) : user.role === "customer" ? (
                <button
                  type="button"
                  disabled={x.open_campaigns >= x.max_open_campaigns}
                  onClick={async () => {
                    try {
                      await startGroupBuy(x.id, 1);
                      setMsg({ text: t("group.started"), tone: "success" });
                      await Promise.all([camps.reload(), templates.reload()]);
                    } catch (e) {
                      setMsg({ text: errorText(e), tone: "error" });
                    }
                  }}
                  className="mt-2 w-full rounded-lg bg-brand py-2 font-semibold text-white disabled:opacity-50"
                >
                  {x.open_campaigns >= x.max_open_campaigns ? t("group.joinExisting") : t("group.startGroup")}
                </button>
              ) : null}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
