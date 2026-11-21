"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, IndianRupee, LayoutGrid, Package, RefreshCw, Store, Users } from "lucide-react";
import { BasketLoader } from "@/components/brand/basket-loader";
import { EmptyState, Kpi, Notice, PageHeader } from "@/components/portal/kpi";
import { DataTable } from "@/components/portal/table";
import { apiClient } from "@/lib/api/client";
import { errorMessage } from "@/lib/i18n/errors";
import { useI18n } from "@/lib/i18n/i18n-context";
import type { AdminOverview, AdminRetailerListItem } from "@/types";

export default function AdminOverviewPage() {
  const { t, money, number, date } = useI18n();
  const [o, setO] = useState<AdminOverview | null>(null);
  const [pending, setPending] = useState<AdminRetailerListItem[]>([]);
  const [msg, setMsg] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [ov, rs] = await Promise.all([apiClient.getAdminOverview(), apiClient.listAdminRetailers({ status: "PENDING" })]);
      setO(ov);
      setPending(rs);
    } catch (e) {
      setMsg({ kind: "error", text: errorMessage(e, t) });
    }
  }, [t]);
  useEffect(() => {
    load();
  }, [load]);

  const decide = async (r: AdminRetailerListItem, status: "VERIFIED" | "REJECTED") => {
    let reason: string | undefined;
    if (status === "REJECTED") {
      reason = window.prompt(t("admin.retailers.rejectReason")) ?? undefined;
      if (!reason || reason.trim().length < 3) return;
    }
    setBusy(r.id);
    try {
      await apiClient.verifyRetailer(r.id, status, reason);
      setMsg({ kind: "ok", text: status === "VERIFIED" ? t("admin.retailers.approved", { name: r.name }) : t("admin.retailers.rejected", { name: r.name }) });
      await load();
    } catch (e) {
      setMsg({ kind: "error", text: errorMessage(e, t) });
    } finally {
      setBusy(null);
    }
  };

  if (!o) return msg ? <Notice kind="error">{msg.text}</Notice> : <BasketLoader />;

  return (
    <div>
      <PageHeader
        title={t("admin.overview.title")}
        subtitle={t("admin.overview.subtitle")}
        actions={<button type="button" onClick={load} className="inline-flex items-center gap-1.5 rounded-lg border bg-white px-3 py-2 text-sm"><RefreshCw className="h-4 w-4" /> {t("common.refresh")}</button>}
      />
      {msg && <Notice kind={msg.kind}>{msg.text}</Notice>}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <Kpi label={t("admin.overview.revenue")} value={money(o.total_revenue_paise)} hint={t("admin.overview.revenueHint", { refunded: money(o.refunded_paise ?? 0) })} icon={<IndianRupee className="h-4 w-4" />} />
        <Kpi label={t("admin.overview.orders")} value={number(o.total_orders)} hint={t("admin.overview.ordersHint", { paid: o.paid_orders ?? 0, pending: o.pending_payment_orders ?? 0 })} icon={<Package className="h-4 w-4" />} />
        <Kpi label={t("admin.overview.customers")} value={number(o.total_customers)} hint={t("admin.overview.customersHint")} icon={<Users className="h-4 w-4" />} />
        <Kpi label={t("admin.overview.retailers")} value={number(o.total_retailers)} hint={t("admin.overview.retailersHint", { n: o.active_retailers ?? 0 })} icon={<Store className="h-4 w-4" />} />
        <Kpi label={t("admin.overview.pending")} value={number(o.pending_verifications)} tone={o.pending_verifications > 0 ? "warn" : "default"} icon={<AlertCircle className="h-4 w-4" />} />
        <Kpi label={t("admin.overview.products")} value={number(o.active_products)} icon={<LayoutGrid className="h-4 w-4" />} />
      </div>
      {(o.excluded_test_records ?? 0) > 0 && (
        <p className="mt-3 text-xs text-muted-foreground">{t("admin.overview.fixturesExcluded", { n: number(o.excluded_test_records ?? 0) })}</p>
      )}

      <section className="mt-8">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">{t("admin.overview.desk")}</h2>
          <Link href="/admin/retailers" className="text-sm text-brand underline">{t("common.viewAll")}</Link>
        </div>
        {pending.length === 0 ? (
          <EmptyState title={t("admin.overview.noPending")} />
        ) : (
          <DataTable head={[t("admin.retailers.store"), t("admin.retailers.owner"), t("onboarding.state"), t("admin.retailers.documents"), t("common.created"), ""]}>
            {pending.map((r) => (
              <tr key={r.id}>
                <td><Link href={`/admin/retailers/${r.id}`} className="font-medium hover:text-brand">{r.name}</Link></td>
                <td className="text-xs">{r.owner_name ?? "—"}<div className="text-muted-foreground">{r.owner_email ?? r.contact_email ?? ""}</div></td>
                <td>{r.state ?? "—"}</td>
                <td>{r.documents_count ?? 0}</td>
                <td className="text-xs text-muted-foreground">{date(r.created_at)}</td>
                <td className="whitespace-nowrap">
                  <button type="button" disabled={busy === r.id} onClick={() => decide(r, "VERIFIED")} className="mr-3 text-xs font-semibold text-brand-dark underline">{t("admin.retailers.approve")}</button>
                  <button type="button" disabled={busy === r.id} onClick={() => decide(r, "REJECTED")} className="text-xs font-semibold text-red-700 underline">{t("admin.retailers.reject")}</button>
                </td>
              </tr>
            ))}
          </DataTable>
        )}
      </section>
    </div>
  );
}
