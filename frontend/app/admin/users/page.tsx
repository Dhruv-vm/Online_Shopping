"use client";

import { useEffect, useState } from "react";
import { BasketLoader } from "@/components/brand/basket-loader";
import { Notice, PageHeader } from "@/components/portal/kpi";
import { DataTable, Pager, Pill } from "@/components/portal/table";
import { adminListUsers, adminSetUserStatus, type AdminUser } from "@/lib/api/marketplace";
import { errorMessage } from "@/lib/i18n/errors";
import { useI18n } from "@/lib/i18n/i18n-context";

const LIMIT = 25;

export default function AdminUsersPage() {
  const { t, date } = useI18n();
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const [fixtures, setFixtures] = useState(false);
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<{ items: AdminUser[]; total: number } | null>(null);
  const [msg, setMsg] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const load = () =>
    adminListUsers({ q: q || undefined, role: role || undefined, include_test_fixtures: fixtures, limit: LIMIT, offset })
      .then(setData)
      .catch((e) => setMsg({ kind: "error", text: errorMessage(e, t) }));

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [role, fixtures, offset]);

  const toggle = async (u: AdminUser) => {
    const reason = window.prompt(u.is_active ? t("admin.users.suspendReason") : t("admin.users.reinstateReason"));
    if (!reason || reason.trim().length < 3) return;
    try {
      await adminSetUserStatus(u.id, !u.is_active, reason.trim());
      setMsg({ kind: "ok", text: u.is_active ? t("admin.users.suspended") : t("admin.users.reinstated") });
      await load();
    } catch (e) {
      setMsg({ kind: "error", text: errorMessage(e, t) });
    }
  };

  return (
    <div>
      <PageHeader title={t("admin.nav.users")} subtitle={t("admin.users.subtitle")} />
      {msg && <Notice kind={msg.kind}>{msg.text}</Notice>}
      <form className="mb-4 flex flex-wrap items-end gap-2" onSubmit={(e) => { e.preventDefault(); setOffset(0); load(); }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("admin.users.search")} className="h-9 w-64 rounded-md border px-3 text-sm" aria-label={t("admin.users.search")} />
        <select value={role} onChange={(e) => { setRole(e.target.value); setOffset(0); }} className="h-9 rounded-md border bg-white px-2 text-sm" aria-label={t("admin.users.role")}>
          <option value="">{t("common.all")}</option>
          <option value="customer">{t("role.customer")}</option>
          <option value="retailer">{t("role.retailer")}</option>
          <option value="admin">{t("role.admin")}</option>
        </select>
        <label className="flex items-center gap-1.5 text-sm"><input type="checkbox" checked={fixtures} onChange={(e) => { setFixtures(e.target.checked); setOffset(0); }} /> {t("admin.showFixtures")}</label>
        <button type="submit" className="h-9 rounded-md bg-brand px-3 text-sm font-semibold text-white">{t("common.search")}</button>
      </form>
      {!data ? <BasketLoader /> : (
        <>
          <DataTable head={[t("admin.users.user"), t("admin.users.role"), t("common.language"), t("common.status"), t("common.created"), ""]}>
            {data.items.map((u) => (
              <tr key={u.id}>
                <td><div className="font-medium">{u.full_name}</div><div className="text-xs text-muted-foreground">{u.email}</div></td>
                <td>{t(`role.${u.role}`)}</td>
                <td>{u.preferred_language ?? "en"}</td>
                <td>{u.is_test_fixture ? <Pill>{t("admin.testFixture")}</Pill> : u.is_active ? <Pill tone="good">{t("admin.users.active")}</Pill> : <Pill tone="bad">{t("admin.users.suspendedLabel")}</Pill>}</td>
                <td className="text-xs text-muted-foreground">{date(u.created_at)}</td>
                <td>
                  {!u.is_test_fixture && (
                    <button type="button" onClick={() => toggle(u)} className={`text-xs font-semibold underline ${u.is_active ? "text-red-700" : "text-brand-dark"}`}>
                      {u.is_active ? t("admin.users.suspend") : t("admin.users.reinstate")}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </DataTable>
          <Pager offset={offset} limit={LIMIT} total={data.total} onPage={setOffset} label={(a, b, n) => t("common.range", { from: a, to: b, total: n })} />
        </>
      )}
    </div>
  );
}
