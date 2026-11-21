"use client";

import { useEffect, useState } from "react";
import { BasketLoader } from "@/components/brand/basket-loader";
import { Notice, PageHeader } from "@/components/portal/kpi";
import { DataTable, Pager, Pill } from "@/components/portal/table";
import { adminListOrders, type AdminOrder } from "@/lib/api/marketplace";
import { errorMessage } from "@/lib/i18n/errors";
import { useI18n } from "@/lib/i18n/i18n-context";

const LIMIT = 25;
const STATUSES = ["PENDING_PAYMENT", "CONFIRMED", "PROCESSING", "PACKED", "SHIPPED", "OUT_FOR_DELIVERY", "DELIVERED", "CANCELLED", "RETURNED"];
const PAY = ["NOT_INITIATED", "PENDING", "SUCCEEDED", "FAILED", "REQUIRES_RECONCILIATION", "PARTIALLY_REFUNDED", "REFUNDED"];

export default function AdminOrdersPage() {
  const { t, money, date } = useI18n();
  const [f, setF] = useState({ q: "", status: "", payment_status: "" });
  const [fixtures, setFixtures] = useState(false);
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<{ items: AdminOrder[]; total: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () =>
    adminListOrders({ q: f.q || undefined, status: f.status || undefined, payment_status: f.payment_status || undefined, include_test_fixtures: fixtures, limit: LIMIT, offset })
      .then(setData)
      .catch((e) => setError(errorMessage(e, t)));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [f.status, f.payment_status, fixtures, offset]);

  return (
    <div>
      <PageHeader title={t("admin.nav.orders")} subtitle={t("admin.orders.subtitle")} />
      {error && <Notice kind="error">{error}</Notice>}
      <form className="mb-4 flex flex-wrap items-end gap-2" onSubmit={(e) => { e.preventDefault(); setOffset(0); load(); }}>
        <input value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })} placeholder={t("admin.orders.search")} aria-label={t("admin.orders.search")} className="h-9 w-64 rounded-md border px-3 text-sm" />
        <select value={f.status} onChange={(e) => { setF({ ...f, status: e.target.value }); setOffset(0); }} className="h-9 rounded-md border bg-white px-2 text-sm" aria-label={t("admin.orders.orderStatus")}>
          <option value="">{t("admin.orders.anyStatus")}</option>
          {STATUSES.map((s) => <option key={s} value={s}>{t(`status.order.${s}`)}</option>)}
        </select>
        <select value={f.payment_status} onChange={(e) => { setF({ ...f, payment_status: e.target.value }); setOffset(0); }} className="h-9 rounded-md border bg-white px-2 text-sm" aria-label={t("admin.orders.paymentStatus")}>
          <option value="">{t("admin.orders.anyPayment")}</option>
          {PAY.map((s) => <option key={s} value={s}>{t(`status.payment.${s}`)}</option>)}
        </select>
        <label className="flex items-center gap-1.5 text-sm"><input type="checkbox" checked={fixtures} onChange={(e) => { setFixtures(e.target.checked); setOffset(0); }} /> {t("admin.showFixtures")}</label>
        <button type="submit" className="h-9 rounded-md bg-brand px-3 text-sm font-semibold text-white">{t("common.search")}</button>
      </form>
      {!data ? <BasketLoader /> : (
        <>
          <DataTable head={[t("admin.orders.order"), t("admin.orders.customer"), t("admin.orders.orderStatus"), t("admin.orders.paymentStatus"), t("common.total"), t("admin.orders.stores"), t("common.created")]}>
            {data.items.map((o) => (
              <tr key={o.id}>
                <td className="font-mono text-xs">{o.order_number}</td>
                <td className="text-xs">{o.customer_email ?? t("admin.orders.guest")}</td>
                <td><Pill tone={o.status === "DELIVERED" ? "good" : o.status === "CANCELLED" ? "bad" : "neutral"}>{t(`status.order.${o.status}`)}</Pill></td>
                <td><Pill tone={o.payment_status === "SUCCEEDED" ? "good" : o.payment_status === "FAILED" ? "bad" : "warn"}>{t(`status.payment.${o.payment_status}`)}</Pill></td>
                <td>{money(o.total_payable_paise)}</td>
                <td>{o.retailer_count}</td>
                <td className="text-xs text-muted-foreground">{date(o.created_at, "datetime")}</td>
              </tr>
            ))}
          </DataTable>
          <Pager offset={offset} limit={LIMIT} total={data.total} onPage={setOffset} label={(a, b, n) => t("common.range", { from: a, to: b, total: n })} />
        </>
      )}
    </div>
  );
}
