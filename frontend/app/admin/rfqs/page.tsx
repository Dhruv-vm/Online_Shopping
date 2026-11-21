"use client";

import { useEffect, useState } from "react";
import { BasketLoader } from "@/components/brand/basket-loader";
import { EmptyState, Notice, PageHeader } from "@/components/portal/kpi";
import { DataTable, Pill } from "@/components/portal/table";
import { adminListRfqs, adminModerateRfq } from "@/lib/api/marketplace";
import type { ExchangeRequest } from "@/lib/api/phase3";
import { errorMessage } from "@/lib/i18n/errors";
import { useI18n } from "@/lib/i18n/i18n-context";

export default function AdminRfqsPage() {
  const { t, money, date } = useI18n();
  const [status, setStatus] = useState("BIDDING_OPEN");
  const [rows, setRows] = useState<ExchangeRequest[] | null>(null);
  const [msg, setMsg] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const load = () => adminListRfqs({ status: status || undefined, limit: 100 }).then((r) => setRows(r.items)).catch((e) => setMsg({ kind: "error", text: errorMessage(e, t) }));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { setRows(null); load(); }, [status]);

  const moderate = async (r: ExchangeRequest) => {
    const reason = window.prompt(t("admin.rfqs.reasonPrompt"));
    if (!reason || reason.trim().length < 5) return;
    try {
      await adminModerateRfq(r.id, reason.trim());
      setMsg({ kind: "ok", text: t("admin.rfqs.closed") });
      await load();
    } catch (e) {
      setMsg({ kind: "error", text: errorMessage(e, t) });
    }
  };

  return (
    <div>
      <PageHeader title={t("admin.nav.rfqs")} subtitle={t("admin.rfqs.subtitle")} actions={
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="h-9 rounded-md border bg-white px-2 text-sm" aria-label={t("common.status")}>
          <option value="">{t("common.all")}</option>
          {["BIDDING_OPEN", "AWARDED", "EXPIRED", "CANCELLED"].map((s) => <option key={s} value={s}>{t(`rfqStatus.${s}`)}</option>)}
        </select>
      } />
      {msg && <Notice kind={msg.kind}>{msg.text}</Notice>}
      {!rows ? <BasketLoader /> : rows.length === 0 ? <EmptyState title={t("admin.rfqs.empty")} /> : (
        <DataTable head={[t("admin.rfqs.request"), t("admin.rfqs.items"), t("admin.rfqs.budget"), t("admin.rfqs.bids"), t("common.status"), t("common.created"), ""]}>
          {rows.map((r) => (
            <tr key={r.id}>
              <td><div className="font-medium">{r.title}</div><div className="text-xs text-muted-foreground">PIN {r.delivery_pincode}</div></td>
              <td className="text-xs">{r.items.map((i) => `${i.quantity}× ${i.name}`).join(", ")}</td>
              <td>{r.budget_limit_paise ? money(r.budget_limit_paise) : "—"}</td>
              <td>{r.bid_count}</td>
              <td><Pill tone={r.status === "BIDDING_OPEN" ? "warn" : r.status === "AWARDED" ? "good" : "neutral"}>{t(`rfqStatus.${r.status}`)}</Pill></td>
              <td className="text-xs text-muted-foreground">{date(r.created_at)}</td>
              <td>{r.status === "BIDDING_OPEN" && <button type="button" onClick={() => moderate(r)} className="text-xs font-semibold text-red-700 underline">{t("admin.rfqs.close")}</button>}</td>
            </tr>
          ))}
        </DataTable>
      )}
    </div>
  );
}
