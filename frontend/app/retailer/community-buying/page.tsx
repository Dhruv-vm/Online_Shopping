"use client";

import { useState } from "react";
import { EmptyState, PageHeader } from "@/components/portal/kpi";
import { errorText, Notice, Status, useLoad } from "@/components/phase3/kit";
import { loadMyListings } from "@/components/phase3/my-listings";
import {
  deactivateGroupBuyTemplate,
  listMyGroupBuyTemplates,
  upsertGroupBuyTemplate,
} from "@/lib/api/marketplace";
import { retailerCampaigns, retailerCancelCampaign, retailerCreateCampaign } from "@/lib/api/phase3";
import { useI18n } from "@/lib/i18n/i18n-context";
import { useLiveUpdates } from "@/lib/realtime";

type Form = { listing_id: string; min: string; max: string; pct: string; hours: string; perMember: string; openCap: string };
const START: Form = { listing_id: "", min: "3", max: "10", pct: "10", hours: "48", perMember: "2", openCap: "3" };

function Inputs({ f, setF, withCap }: { f: Form; setF: (f: Form) => void; withCap?: boolean }) {
  const { t } = useI18n();
  const fields: [keyof Form, string][] = [
    ["min", "group.minMembers"],
    ["max", "group.maxMembers"],
    ["pct", "group.discountPct"],
    ["hours", "group.durationHours"],
    ["perMember", "group.maxPerMember"],
    ...(withCap ? ([["openCap", "group.openCap"]] as [keyof Form, string][]) : []),
  ];
  return (
    <>
      {fields.map(([k, label]) => (
        <label key={k} className="text-xs font-medium">
          {t(label)}
          <input type="number" min={1} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} className="mt-1 h-9 w-full rounded-md border px-2 text-sm" />
        </label>
      ))}
    </>
  );
}

export default function RetailerCommunityBuyingPage() {
  const { t, money } = useI18n();
  const camps = useLoad(() => retailerCampaigns());
  useLiveUpdates(["group_buy."], () => void camps.refresh());
  const templates = useLoad(() => listMyGroupBuyTemplates());
  const listings = useLoad(() => loadMyListings());
  const [camp, setCamp] = useState<Form>(START);
  const [tpl, setTpl] = useState<Form>(START);
  const [msg, setMsg] = useState<{ text: string; tone: "error" | "success" } | null>(null);

  const listingSelect = (f: Form, set: (f: Form) => void) => (
    <label className="text-xs font-medium sm:col-span-2">
      {t("common.product")}
      <select value={f.listing_id} onChange={(e) => set({ ...f, listing_id: e.target.value })} className="mt-1 h-9 w-full rounded-md border bg-white px-2 text-sm">
        <option value="">{t("group.chooseListing")}</option>
        {listings.data?.map((l) => (
          <option key={l.id} value={l.id}>{l.product_name} — {l.variant_name}</option>
        ))}
      </select>
    </label>
  );

  return (
    <div className="space-y-6">
      <PageHeader title={t("retailer.nav.groupBuys")} subtitle={t("group.retailerSubtitle")} />
      {msg && <Notice text={msg.text} tone={msg.tone} />}

      <div className="grid gap-6 xl:grid-cols-2">
        <section className="rounded-xl border bg-white p-5">
          <h2 className="font-semibold">{t("group.launchTitle")}</h2>
          <p className="mb-3 text-xs text-muted-foreground">{t("group.launchBody")}</p>
          <div className="grid gap-3 sm:grid-cols-2">
            {listingSelect(camp, setCamp)}
            <Inputs f={camp} setF={setCamp} />
          </div>
          <button
            type="button"
            disabled={!camp.listing_id}
            onClick={async () => {
              try {
                await retailerCreateCampaign({ listing_id: camp.listing_id, min_participants: +camp.min, max_participants: +camp.max, discount_percent: +camp.pct, duration_hours: +camp.hours, max_quantity_per_member: +camp.perMember });
                setMsg({ text: t("group.launched"), tone: "success" });
                await camps.reload();
              } catch (e) {
                setMsg({ text: errorText(e), tone: "error" });
              }
            }}
            className="mt-4 rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"
          >
            {t("group.launch")}
          </button>
        </section>

        <section className="rounded-xl border bg-white p-5">
          <h2 className="font-semibold">{t("group.templateTitle")}</h2>
          <p className="mb-3 text-xs text-muted-foreground">{t("group.templateBody")}</p>
          <div className="grid gap-3 sm:grid-cols-2">
            {listingSelect(tpl, setTpl)}
            <Inputs f={tpl} setF={setTpl} withCap />
          </div>
          <button
            type="button"
            disabled={!tpl.listing_id}
            onClick={async () => {
              try {
                await upsertGroupBuyTemplate({ listing_id: tpl.listing_id, min_participants: +tpl.min, max_participants: +tpl.max, discount_percent: +tpl.pct, duration_hours: +tpl.hours, max_quantity_per_member: +tpl.perMember, max_open_campaigns: +tpl.openCap });
                setMsg({ text: t("group.templateSaved"), tone: "success" });
                await templates.reload();
              } catch (e) {
                setMsg({ text: errorText(e), tone: "error" });
              }
            }}
            className="mt-4 rounded-lg bg-brand-dark px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"
          >
            {t("group.publishTemplate")}
          </button>
          <ul className="mt-4 divide-y text-sm">
            {templates.data?.items.map((x) => (
              <li key={x.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <span>
                  <span className="font-medium">{x.product_name}</span>{" "}
                  <span className="text-xs text-muted-foreground">
                    {money(x.group_price_paise)} (−{x.discount_percent}%) · {x.min_participants}–{x.max_participants} · {t("group.openNow", { n: x.open_campaigns })}
                  </span>
                </span>
                {x.is_active ? (
                  <button type="button" className="text-xs text-red-700 underline" onClick={async () => { await deactivateGroupBuyTemplate(x.id); await templates.reload(); }}>
                    {t("group.stopOffering")}
                  </button>
                ) : (
                  <span className="text-xs text-muted-foreground">{t("group.inactive")}</span>
                )}
              </li>
            ))}
          </ul>
        </section>
      </div>

      <section className="rounded-xl border bg-white p-5">
        <h2 className="mb-3 font-semibold">{t("group.myCampaigns")}</h2>
        <Status loading={camps.loading} error={camps.error} onRetry={camps.reload} />
        {camps.data && camps.data.items.length === 0 && <EmptyState title={t("group.noCampaigns")} />}
        {camps.data && camps.data.items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead className="text-left text-xs text-muted-foreground">
                <tr>
                  <th className="py-2">{t("group.campaign")}</th>
                  <th>{t("group.groupPrice")}</th>
                  <th>{t("group.members")}</th>
                  <th>{t("common.status")}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {camps.data.items.map((c) => (
                  <tr key={c.id} className="border-t">
                    <td className="py-2">
                      {c.title}
                      {c.started_by_customer && (
                        <span className="ml-2 rounded bg-brand-light px-1.5 text-[11px] text-brand-dark">{t("group.startedByCustomer")}</span>
                      )}
                    </td>
                    <td>{money(c.group_price_paise)} <span className="text-xs text-muted-foreground">(−{c.discount_percent}%)</span></td>
                    <td>{c.current_participants}/{c.min_participants}–{c.max_participants}</td>
                    <td>{t(`groupStatus.${c.status}`)}</td>
                    <td>
                      {c.status === "OPEN" && (
                        <button type="button" onClick={async () => { await retailerCancelCampaign(c.id); await camps.reload(); }} className="text-xs underline">
                          {t("common.cancel")}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
