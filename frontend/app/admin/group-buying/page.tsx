"use client";

import { useEffect, useState } from "react";
import { BasketLoader } from "@/components/brand/basket-loader";
import { EmptyState, Notice, PageHeader } from "@/components/portal/kpi";
import { DataTable, Pill } from "@/components/portal/table";
import { adminCancelCampaign, adminListCampaigns } from "@/lib/api/marketplace";
import type { GroupBuyCampaign } from "@/lib/api/phase3";
import { errorMessage } from "@/lib/i18n/errors";
import { useI18n } from "@/lib/i18n/i18n-context";

export default function AdminGroupBuyingPage() {
  const { t, money, date } = useI18n();
  const [status, setStatus] = useState("OPEN");
  const [rows, setRows] = useState<GroupBuyCampaign[] | null>(null);
  const [msg, setMsg] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const load = () => adminListCampaigns({ status: status || undefined, limit: 100 }).then((r) => setRows(r.items)).catch((e) => setMsg({ kind: "error", text: errorMessage(e, t) }));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { setRows(null); load(); }, [status]);

  return (
    <div>
      <PageHeader title={t("admin.nav.groupBuying")} subtitle={t("admin.groups.subtitle")} actions={
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="h-9 rounded-md border bg-white px-2 text-sm" aria-label={t("common.status")}>
          <option value="">{t("common.all")}</option>
          {["OPEN", "SUCCESSFUL", "FAILED", "CANCELLED"].map((s) => <option key={s} value={s}>{t(`groupStatus.${s}`)}</option>)}
        </select>
      } />
      {msg && <Notice kind={msg.kind}>{msg.text}</Notice>}
      {!rows ? <BasketLoader /> : rows.length === 0 ? <EmptyState title={t("group.noCampaigns")} /> : (
        <DataTable head={[t("group.campaign"), t("nav.retailers"), t("group.groupPrice"), t("group.members"), t("common.status"), t("admin.groups.ends"), ""]}>
          {rows.map((c) => (
            <tr key={c.id}>
              <td><div className="font-medium">{c.title}</div>{c.started_by_customer && <span className="text-[11px] text-brand-dark">{t("group.startedByCustomer")}</span>}</td>
              <td className="text-xs">{c.retailer_name}</td>
              <td>{money(c.group_price_paise)} <span className="text-xs text-muted-foreground">(−{c.discount_percent}%)</span></td>
              <td>{c.current_participants}/{c.min_participants}–{c.max_participants}</td>
              <td><Pill tone={c.status === "SUCCESSFUL" ? "good" : c.status === "OPEN" ? "warn" : "neutral"}>{t(`groupStatus.${c.status}`)}</Pill></td>
              <td className="text-xs text-muted-foreground">{date(c.expires_at, "datetime")}</td>
              <td>{c.status === "OPEN" && (
                <button type="button" className="text-xs font-semibold text-red-700 underline" onClick={async () => {
                  if (!window.confirm(t("admin.groups.confirmCancel"))) return;
                  try { await adminCancelCampaign(c.id); setMsg({ kind: "ok", text: t("admin.groups.cancelled") }); await load(); } catch (e) { setMsg({ kind: "error", text: errorMessage(e, t) }); }
                }}>{t("common.cancel")}</button>
              )}</td>
            </tr>
          ))}
        </DataTable>
      )}
    </div>
  );
}
