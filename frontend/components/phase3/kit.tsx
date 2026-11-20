"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiClientError } from "@/lib/api/client";
import { useI18n } from "@/lib/i18n/i18n-context";

export function errorText(e: unknown): string {
  if (e instanceof ApiClientError) return `${e.message} (${e.code})`;
  return e instanceof Error ? e.message : "Unexpected error";
}

/** Load data with loading/error state; `reload` re-runs the loader. */
export function useLoad<T>(loader: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(loader, deps);
  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await run());
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  }, [run]);
  useEffect(() => {
    void reload();
  }, [reload]);
  return { data, setData, error, setError, loading, reload };
}

export function Status({ loading, error, onRetry }: { loading: boolean; error: string | null; onRetry?: () => void }) {
  const { t } = useI18n();
  if (loading) return <p className="py-6 text-sm text-gray-500">{t("common.loading")}</p>;
  if (error)
    return (
      <div role="alert" className="my-3 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
        {t("common.error")}: {error}
        {onRetry && (
          <button className="ml-3 underline" onClick={onRetry}>
            {t("common.retry")}
          </button>
        )}
      </div>
    );
  return null;
}

export function Notice({ text, tone = "info" }: { text: string | null; tone?: "info" | "error" | "success" }) {
  if (!text) return null;
  const cls = tone === "error" ? "border-red-200 bg-red-50 text-red-700" : tone === "success" ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-blue-200 bg-blue-50 text-blue-800";
  return <div role={tone === "error" ? "alert" : "status"} className={`my-3 rounded border p-3 text-sm ${cls}`}>{text}</div>;
}

export function Countdown({ seconds }: { seconds: number }) {
  const [left, setLeft] = useState(seconds);
  useEffect(() => setLeft(seconds), [seconds]);
  useEffect(() => {
    if (left <= 0) return;
    const id = setInterval(() => setLeft((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(id);
  }, [left]);
  const h = Math.floor(left / 3600), m = Math.floor((left % 3600) / 60), s = left % 60;
  return <span className="font-mono tabular-nums">{h > 0 ? `${h}h ` : ""}{String(m).padStart(2, "0")}:{String(s).padStart(2, "0")}</span>;
}

export function PageTitle({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-5">
      <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
      {subtitle && <p className="mt-1 text-sm text-gray-600">{subtitle}</p>}
    </div>
  );
}

export const rupeesToPaise = (v: string) => Math.round(parseFloat(v || "0") * 100);
