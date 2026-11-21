import type { ReactNode } from "react";

export function Kpi({ label, value, hint, icon, tone = "default" }: { label: string; value: ReactNode; hint?: string; icon?: ReactNode; tone?: "default" | "warn" | "good" }) {
  const toneCls = tone === "warn" ? "border-amber-200 bg-amber-50" : tone === "good" ? "border-brand/20 bg-brand-light/40" : "bg-white";
  return (
    <div className={`rounded-xl border p-4 ${toneCls}`}>
      <div className="flex items-center justify-between text-muted-foreground">
        <span className="text-xs font-semibold uppercase tracking-wide">{label}</span>
        {icon}
      </div>
      <div className="mt-2 text-2xl font-bold text-charcoal">{value}</div>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-bold text-charcoal">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </header>
  );
}

export function Notice({ kind, children }: { kind: "ok" | "error" | "info"; children: ReactNode }) {
  const cls =
    kind === "ok"
      ? "border-brand/30 bg-brand-light text-brand-dark"
      : kind === "error"
        ? "border-red-200 bg-red-50 text-red-800"
        : "border-sky-200 bg-sky-50 text-sky-900";
  return (
    <p role={kind === "error" ? "alert" : "status"} className={`mb-4 rounded-md border p-3 text-sm ${cls}`}>
      {children}
    </p>
  );
}

export function EmptyState({ title, body, action }: { title: string; body?: string; action?: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed bg-white p-8 text-center">
      <p className="font-semibold">{title}</p>
      {body && <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">{body}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
