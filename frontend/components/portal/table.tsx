import type { ReactNode } from "react";

export function DataTable({ head, children, minWidth = 720 }: { head: ReactNode[]; children: ReactNode; minWidth?: number }) {
  return (
    <div className="overflow-x-auto rounded-xl border bg-white">
      <table className="w-full text-sm" style={{ minWidth }}>
        <thead className="bg-surface text-left text-xs text-muted-foreground">
          <tr>
            {head.map((h, i) => (
              <th key={i} className="px-4 py-3 font-semibold">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="[&>tr]:border-t [&_td]:px-4 [&_td]:py-3">{children}</tbody>
      </table>
    </div>
  );
}

export function Pager({ offset, limit, total, onPage, label }: { offset: number; limit: number; total: number; onPage: (o: number) => void; label: (from: number, to: number, total: number) => string }) {
  if (total <= limit) return null;
  return (
    <div className="mt-3 flex items-center justify-between text-sm">
      <span className="text-muted-foreground">{label(offset + 1, Math.min(offset + limit, total), total)}</span>
      <span className="flex gap-2">
        <button type="button" disabled={offset === 0} onClick={() => onPage(Math.max(0, offset - limit))} className="rounded-md border px-3 py-1 disabled:opacity-40">‹</button>
        <button type="button" disabled={offset + limit >= total} onClick={() => onPage(offset + limit)} className="rounded-md border px-3 py-1 disabled:opacity-40">›</button>
      </span>
    </div>
  );
}

export function Pill({ tone = "neutral", children }: { tone?: "good" | "warn" | "bad" | "neutral"; children: ReactNode }) {
  const cls = { good: "bg-brand-light text-brand-dark", warn: "bg-amber-100 text-amber-900", bad: "bg-red-100 text-red-800", neutral: "bg-muted text-charcoal" }[tone];
  return <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${cls}`}>{children}</span>;
}
