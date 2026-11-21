"use client";

import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { BasketLoader } from "@/components/brand/basket-loader";
import { Kpi, Notice, PageHeader } from "@/components/portal/kpi";
import { DataTable, Pill } from "@/components/portal/table";
import { adminSystemHealth, type SystemHealth } from "@/lib/api/marketplace";
import { errorMessage } from "@/lib/i18n/errors";
import { useI18n } from "@/lib/i18n/i18n-context";

const TONE = { ok: "good", degraded: "warn", down: "bad", not_configured: "neutral" } as const;

export default function AdminSettingsPage() {
  const { t, date, number } = useI18n();
  const [h, setH] = useState<SystemHealth | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = () => adminSystemHealth().then(setH).catch((e) => setError(errorMessage(e, t)));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, []);

  return (
    <div>
      <PageHeader
        title={t("admin.health.title")}
        subtitle={t("admin.health.subtitle")}
        actions={<button type="button" onClick={load} className="inline-flex items-center gap-1.5 rounded-lg border bg-white px-3 py-2 text-sm"><RefreshCw className="h-4 w-4" /> {t("common.refresh")}</button>}
      />
      {error && <Notice kind="error">{error}</Notice>}
      {!h ? <BasketLoader /> : (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Kpi label={t("admin.health.outboxPending")} value={number(h.outbox_pending)} hint={h.oldest_pending_event_seconds != null ? t("admin.health.oldest", { s: h.oldest_pending_event_seconds }) : undefined} tone={h.outbox_pending > 100 ? "warn" : "default"} />
            <Kpi label={t("admin.health.outboxFailed")} value={number(h.outbox_failed)} tone={h.outbox_failed > 0 ? "warn" : "default"} />
            <Kpi label={t("admin.health.quarantined")} value={number(h.quarantined_test_records)} hint={t("admin.health.quarantinedHint")} />
            <Kpi label={t("admin.health.checked")} value={<span className="text-base">{date(h.checked_at, "datetime")}</span>} />
          </div>
          <DataTable head={[t("admin.health.component"), t("common.status"), t("admin.health.detail")]} minWidth={560}>
            {h.components.map((c) => (
              <tr key={c.name}>
                <td className="font-medium">{c.name}</td>
                <td><Pill tone={TONE[c.status]}>{t(`health.${c.status}`)}</Pill></td>
                <td className="text-sm text-muted-foreground">{c.detail}</td>
              </tr>
            ))}
          </DataTable>
          <section>
            <h2 className="mb-2 font-semibold">{t("admin.health.jobs")}</h2>
            {Object.keys(h.background_jobs).length === 0 ? (
              <p className="text-sm text-muted-foreground">{t("admin.health.noJobs")}</p>
            ) : (
              <DataTable head={[t("admin.health.job"), t("admin.health.lastRun"), t("common.status")]} minWidth={560}>
                {Object.entries(h.background_jobs).map(([name, j]) => (
                  <tr key={name}>
                    <td className="font-mono text-xs">{name}</td>
                    <td className="text-xs">{date(j.last_run_at, "datetime")}</td>
                    <td>{j.last_ok ? <Pill tone="good">{t("health.ok")}</Pill> : <Pill tone="bad">{j.last_error ?? t("health.down")}</Pill>}</td>
                  </tr>
                ))}
              </DataTable>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
