"use client";

import { useEffect, useState } from "react";
import { BasketLoader } from "@/components/brand/basket-loader";
import { EmptyState, Notice, PageHeader } from "@/components/portal/kpi";
import { DataTable, Pager, Pill } from "@/components/portal/table";
import { adminAuditLogs, type AuditEntry } from "@/lib/api/marketplace";
import { errorMessage } from "@/lib/i18n/errors";
import { useI18n } from "@/lib/i18n/i18n-context";

const LIMIT = 50;

export default function AdminAuditLogsPage() {
  const { t, date } = useI18n();
  const [actor, setActor] = useState("");
  const [entity, setEntity] = useState("");
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<{ items: AuditEntry[]; total: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = () =>
    adminAuditLogs({ actor: actor || undefined, entity_id: entity || undefined, limit: LIMIT, offset })
      .then(setData)
      .catch((e) => setError(errorMessage(e, t)));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [offset]);

  return (
    <div>
      <PageHeader title={t("admin.nav.audit")} subtitle={t("admin.audit.subtitle")} />
      {error && <Notice kind="error">{error}</Notice>}
      <form className="mb-4 flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); setOffset(0); load(); }}>
        <input value={actor} onChange={(e) => setActor(e.target.value)} placeholder={t("admin.audit.actor")} aria-label={t("admin.audit.actor")} className="h-9 w-56 rounded-md border px-3 text-sm" />
        <input value={entity} onChange={(e) => setEntity(e.target.value)} placeholder={t("admin.audit.entity")} aria-label={t("admin.audit.entity")} className="h-9 w-80 rounded-md border px-3 font-mono text-xs" />
        <button type="submit" className="h-9 rounded-md bg-brand px-3 text-sm font-semibold text-white">{t("common.search")}</button>
      </form>
      {!data ? <BasketLoader /> : data.items.length === 0 ? <EmptyState title={t("admin.audit.empty")} /> : (
        <>
          <DataTable head={[t("admin.audit.when"), t("admin.audit.actor"), t("admin.audit.action"), t("admin.audit.entity"), t("common.status")]}>
            {data.items.map((a) => (
              <tr key={a.id}>
                <td className="whitespace-nowrap text-xs">{date(a.created_at, "datetime")}</td>
                <td className="text-xs">{a.actor_email ?? "—"}</td>
                <td><span className="font-mono text-xs"><strong>{a.method}</strong> {a.route.replace("/api/v1", "")}</span></td>
                <td className="font-mono text-[11px] text-muted-foreground">{a.entity_id ?? "—"}</td>
                <td><Pill tone="good">{a.status_code}</Pill></td>
              </tr>
            ))}
          </DataTable>
          <Pager offset={offset} limit={LIMIT} total={data.total} onPage={setOffset} label={(x, y, n) => t("common.range", { from: x, to: y, total: n })} />
        </>
      )}
    </div>
  );
}
