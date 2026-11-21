"use client";

import { useEffect, useState } from "react";
import { BasketLoader } from "@/components/brand/basket-loader";
import { EmptyState, Notice, PageHeader } from "@/components/portal/kpi";
import { DataTable, Pill } from "@/components/portal/table";
import { adminListAuctions } from "@/lib/api/marketplace";
import type { Auction } from "@/lib/api/phase3";
import { errorMessage } from "@/lib/i18n/errors";
import { useI18n } from "@/lib/i18n/i18n-context";

export default function AdminAuctionsPage() {
  const { t, money, date } = useI18n();
  const [status, setStatus] = useState("");
  const [rows, setRows] = useState<Auction[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setRows(null);
    adminListAuctions({ status: status || undefined, limit: 100 }).then((r) => setRows(r.items)).catch((e) => setError(errorMessage(e, t)));
  }, [status, t]);
  return (
    <div>
      <PageHeader title={t("admin.nav.auctions")} subtitle={t("admin.auctions.subtitle")} actions={
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="h-9 rounded-md border bg-white px-2 text-sm" aria-label={t("common.status")}>
          <option value="">{t("common.all")}</option>
          {["ACTIVE", "COMPLETED", "NO_BIDS", "AWARDED", "CANCELLED"].map((s) => <option key={s} value={s}>{t(`auctionStatus.${s}`)}</option>)}
        </select>
      } />
      {error && <Notice kind="error">{error}</Notice>}
      {!rows ? <BasketLoader /> : rows.length === 0 ? <EmptyState title={t("admin.auctions.empty")} /> : (
        <DataTable head={[t("admin.auctions.started"), "PIN", t("admin.rfqs.items"), t("admin.auctions.reference"), t("admin.auctions.best"), t("admin.rfqs.bids"), t("common.status")]}>
          {rows.map((a) => (
            <tr key={a.id}>
              <td className="text-xs">{date(a.starts_at, "datetime")}</td>
              <td>{a.pincode}</td>
              <td className="text-xs">{a.items.map((i) => `${i.quantity}× ${i.product_name}`).join(", ")}</td>
              <td>{money(a.reference_total_paise)}</td>
              <td>{a.best_bid_paise != null ? money(a.best_bid_paise) : "—"}</td>
              <td>{a.bid_count}</td>
              <td><Pill tone={a.status === "AWARDED" ? "good" : a.status === "ACTIVE" ? "warn" : "neutral"}>{t(`auctionStatus.${a.status}`)}</Pill></td>
            </tr>
          ))}
        </DataTable>
      )}
    </div>
  );
}
