"use client";

import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Circle, FileText, Upload } from "lucide-react";
import { BasketLoader } from "@/components/brand/basket-loader";
import { Field, TextInput } from "@/components/forms/field";
import { apiClient } from "@/lib/api/client";
import {
  fileToBase64,
  listRetailerDocuments,
  resubmitVerification,
  submitRetailerDocument,
  type DocumentType,
  type RetailerDocument,
} from "@/lib/api/marketplace";
import { errorMessage } from "@/lib/i18n/errors";
import { useI18n } from "@/lib/i18n/i18n-context";
import { GSTIN_PATTERN } from "@/lib/india";
import type { RetailerProfile } from "@/types";

const DOC_TYPES: DocumentType[] = ["GSTIN_CERTIFICATE", "PAN", "TRADE_LICENSE", "ADDRESS_PROOF", "FSSAI", "OTHER"];
const ACCEPT = "application/pdf,image/jpeg,image/png,image/webp";

export default function RetailerOnboardingPage() {
  const { t, date } = useI18n();
  const [profile, setProfile] = useState<RetailerProfile | null>(null);
  const [docs, setDocs] = useState<RetailerDocument[]>([]);
  const [gstin, setGstin] = useState("");
  const [docType, setDocType] = useState<DocumentType>("GSTIN_CERTIFICATE");
  const [docNumber, setDocNumber] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const [p, d] = await Promise.all([apiClient.getRetailerProfile(), listRetailerDocuments().catch(() => [])]);
    setProfile(p);
    setGstin(p.gstin ?? "");
    setDocs(d);
  }, []);

  useEffect(() => {
    load().catch((e) => setMsg({ ok: false, text: errorMessage(e, t) }));
  }, [load, t]);

  if (!profile) return <BasketLoader />;

  const checklist = [
    { k: "onboarding.check.store", done: !!profile.name && !!profile.description },
    { k: "onboarding.check.address", done: !!profile.business_address && !!profile.state },
    { k: "onboarding.check.contact", done: !!profile.contact_phone && !!profile.contact_email },
    { k: "onboarding.check.gstin", done: !!profile.gstin },
    { k: "onboarding.check.documents", done: docs.length > 0 },
  ];

  const saveGstin = async (e: React.FormEvent) => {
    e.preventDefault();
    const v = gstin.trim().toUpperCase();
    if (v && !GSTIN_PATTERN.test(v)) {
      setMsg({ ok: false, text: t("validation.gstin") });
      return;
    }
    setBusy(true);
    try {
      setProfile(await apiClient.updateRetailerProfile({ gstin: v }));
      setMsg({ ok: true, text: t("onboarding.gstinSaved") });
    } catch (err) {
      setMsg({ ok: false, text: errorMessage(err, t) });
    } finally {
      setBusy(false);
    }
  };

  const upload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file && !docNumber.trim()) {
      setMsg({ ok: false, text: t("onboarding.docNeedsEvidence") });
      return;
    }
    if (file && file.size > 5 * 1024 * 1024) {
      setMsg({ ok: false, text: t("errors.FILE_TOO_LARGE") });
      return;
    }
    setBusy(true);
    try {
      await submitRetailerDocument({
        document_type: docType,
        document_number: docNumber.trim() || undefined,
        ...(file ? { content_base64: await fileToBase64(file), content_type: file.type as "application/pdf" } : {}),
      });
      setFile(null);
      setDocNumber("");
      const input = document.getElementById("doc-file") as HTMLInputElement | null;
      if (input) input.value = "";
      setMsg({ ok: true, text: t("onboarding.docSubmitted") });
      await load();
    } catch (err) {
      setMsg({ ok: false, text: errorMessage(err, t) });
    } finally {
      setBusy(false);
    }
  };

  const resubmit = async () => {
    setBusy(true);
    try {
      await resubmitVerification();
      setMsg({ ok: true, text: t("onboarding.resubmitted") });
      await load();
    } catch (err) {
      setMsg({ ok: false, text: errorMessage(err, t) });
    } finally {
      setBusy(false);
    }
  };

  const status = profile.verification_status;
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">{t("onboarding.title")}</h1>
        <p className="text-sm text-muted-foreground">{t("onboarding.subtitle")}</p>
      </header>
      {msg && (
        <p role="status" className={`rounded-md border p-3 text-sm ${msg.ok ? "border-brand/30 bg-brand-light text-brand-dark" : "border-red-200 bg-red-50 text-red-800"}`}>
          {msg.text}
        </p>
      )}

      <section className="rounded-xl border bg-white p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">{t("onboarding.currentStatus")}</p>
            <p className="text-lg font-bold">{t(`retailer.status.${status}.title`)}</p>
            <p className="text-sm text-muted-foreground">{t(`retailer.status.${status}.body`)}</p>
            {status === "REJECTED" && profile.rejection_reason && (
              <p className="mt-2 rounded-md bg-red-50 p-2 text-sm text-red-800">
                {t("onboarding.reason")}: {profile.rejection_reason}
              </p>
            )}
          </div>
          {status === "REJECTED" && (
            <button type="button" disabled={busy} onClick={resubmit} className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
              {t("onboarding.resubmit")}
            </button>
          )}
        </div>
        <ul className="mt-5 grid gap-2 sm:grid-cols-2">
          {checklist.map((c) => (
            <li key={c.k} className="flex items-center gap-2 text-sm">
              {c.done ? <CheckCircle2 className="h-4 w-4 text-brand" /> : <Circle className="h-4 w-4 text-muted-foreground" />}
              {t(c.k)}
            </li>
          ))}
        </ul>
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <form onSubmit={saveGstin} className="space-y-4 rounded-xl border bg-white p-5">
          <h2 className="font-semibold">{t("onboarding.gstinTitle")}</h2>
          <Field id="gstin" label="GSTIN" hint={t("onboarding.gstinHint")}>
            <TextInput id="gstin" value={gstin} onChange={(e) => setGstin(e.target.value)} maxLength={15} className="uppercase" />
          </Field>
          <button type="submit" disabled={busy} className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">{t("common.save")}</button>
        </form>

        <form onSubmit={upload} className="space-y-4 rounded-xl border bg-white p-5">
          <h2 className="font-semibold">{t("onboarding.uploadTitle")}</h2>
          <Field id="doc-type" label={t("onboarding.docType")}>
            <select id="doc-type" value={docType} onChange={(e) => setDocType(e.target.value as DocumentType)} className="h-11 w-full rounded-lg border bg-white px-3 text-sm">
              {DOC_TYPES.map((d) => (
                <option key={d} value={d}>{t(`doc.${d}`)}</option>
              ))}
            </select>
          </Field>
          <Field id="doc-number" label={`${t("onboarding.docNumber")} (${t("common.optional")})`}>
            <TextInput id="doc-number" value={docNumber} onChange={(e) => setDocNumber(e.target.value)} />
          </Field>
          <Field id="doc-file" label={t("onboarding.docFile")} hint={t("onboarding.docFileHint")}>
            <input id="doc-file" type="file" accept={ACCEPT} onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="block w-full text-sm" />
          </Field>
          <button type="submit" disabled={busy} className="inline-flex items-center gap-2 rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
            <Upload className="h-4 w-4" /> {t("onboarding.submitDoc")}
          </button>
        </form>
      </section>

      <section className="rounded-xl border bg-white p-5">
        <h2 className="font-semibold">{t("onboarding.submittedDocs")}</h2>
        {docs.length === 0 ? (
          <p className="mt-2 text-sm text-muted-foreground">{t("onboarding.noDocs")}</p>
        ) : (
          <ul className="mt-3 divide-y">
            {docs.map((d) => (
              <li key={d.id} className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm">
                <span className="flex items-center gap-2">
                  <FileText className="h-4 w-4 text-brand" />
                  <span className="font-medium">{t(`doc.${d.document_type}`)}</span>
                  {d.document_number && <span className="text-muted-foreground">· {d.document_number}</span>}
                  {d.has_file && <span className="rounded bg-muted px-1.5 text-[11px]">{t("onboarding.fileAttached")}</span>}
                </span>
                <span className="flex items-center gap-3">
                  <span className="text-xs text-muted-foreground">{date(d.created_at)}</span>
                  <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${d.status === "VERIFIED" ? "bg-brand-light text-brand-dark" : d.status === "REJECTED" ? "bg-red-100 text-red-800" : "bg-amber-100 text-amber-900"}`}>
                    {t(`docStatus.${d.status}`)}
                  </span>
                </span>
                {d.rejection_reason && <p className="w-full text-xs text-red-700">{d.rejection_reason}</p>}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
