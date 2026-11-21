"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { CheckCircle2 } from "lucide-react";
import { Field, TextInput } from "@/components/forms/field";
import { apiClient } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/auth-context";
import { errorMessage } from "@/lib/i18n/errors";
import { useI18n } from "@/lib/i18n/i18n-context";
import { GSTIN_PATTERN, INDIAN_STATES } from "@/lib/india";

export default function RetailerRegisterPage() {
  const router = useRouter();
  const { registerRetailer, isAuthenticated, user } = useAuth();
  const { t } = useI18n();
  const [f, setF] = useState({
    full_name: "",
    email: "",
    phone: "",
    password: "",
    confirm: "",
    store_name: "",
    state: "KA",
    business_address: "",
    description: "",
    gstin: "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (isAuthenticated && user?.role === "retailer") router.replace("/retailer");
  }, [isAuthenticated, user?.role, router]);

  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setF((p) => ({ ...p, [k]: e.target.value }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (f.full_name.trim().length < 2) errs.full_name = t("validation.name");
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(f.email.trim())) errs.email = t("validation.email");
    if (!/^\+?[0-9]{10,13}$/.test(f.phone.replace(/\s/g, ""))) errs.phone = t("validation.phone");
    if (f.password.length < 8) errs.password = t("validation.password");
    if (f.password !== f.confirm) errs.confirm = t("validation.passwordMatch");
    if (f.store_name.trim().length < 2) errs.store_name = t("validation.storeName");
    if (f.business_address.trim().length < 5) errs.business_address = t("validation.address");
    if (f.gstin && !GSTIN_PATTERN.test(f.gstin.trim().toUpperCase())) errs.gstin = t("validation.gstin");
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setBusy(true);
    setFormError(null);
    try {
      await registerRetailer({
        email: f.email.trim(),
        password: f.password,
        full_name: f.full_name.trim(),
        phone: f.phone.replace(/\s/g, ""),
        store_name: f.store_name.trim(),
        state: f.state,
        business_address: f.business_address.trim(),
        description: f.description.trim() || undefined,
      });
      if (f.gstin.trim()) {
        await apiClient.updateRetailerProfile({ gstin: f.gstin.trim().toUpperCase() }).catch(() => undefined);
      }
      router.replace("/retailer/onboarding");
    } catch (err) {
      setFormError(errorMessage(err, t));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="container-page grid gap-10 py-10 lg:grid-cols-[1fr_1.3fr]">
      <section className="space-y-5">
        <h1 className="text-3xl font-bold">{t("onboarding.registerTitle")}</h1>
        <p className="text-muted-foreground">{t("onboarding.registerBody")}</p>
        <ol className="space-y-3">
          {["onboarding.step1", "onboarding.step2", "onboarding.step3", "onboarding.step4"].map((k, i) => (
            <li key={k} className="flex items-start gap-3">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand text-xs font-bold text-white">{i + 1}</span>
              <span className="text-sm">{t(k)}</span>
            </li>
          ))}
        </ol>
        <p className="flex items-start gap-2 rounded-lg border border-brand/30 bg-brand-light p-3 text-sm text-brand-dark">
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" /> {t("onboarding.reviewNote")}
        </p>
      </section>
      <section className="rounded-2xl border bg-white p-6 shadow-sm sm:p-8">
        {formError && <p role="alert" className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">{formError}</p>}
        <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2" noValidate>
          <h2 className="text-lg font-semibold sm:col-span-2">{t("onboarding.ownerDetails")}</h2>
          <Field id="full_name" label={t("onboarding.ownerName")} error={errors.full_name}>
            <TextInput id="full_name" value={f.full_name} onChange={set("full_name")} autoComplete="name" />
          </Field>
          <Field id="phone" label={t("auth.phone")} error={errors.phone}>
            <TextInput id="phone" type="tel" value={f.phone} onChange={set("phone")} placeholder="+91 98xxxxxxxx" />
          </Field>
          <Field id="email" label={t("auth.email")} error={errors.email}>
            <TextInput id="email" type="email" value={f.email} onChange={set("email")} autoComplete="email" />
          </Field>
          <div className="hidden sm:block" />
          <Field id="password" label={t("auth.password")} hint={t("validation.password")} error={errors.password}>
            <TextInput id="password" type="password" value={f.password} onChange={set("password")} autoComplete="new-password" />
          </Field>
          <Field id="confirm" label={t("auth.confirmPassword")} error={errors.confirm}>
            <TextInput id="confirm" type="password" value={f.confirm} onChange={set("confirm")} autoComplete="new-password" />
          </Field>
          <h2 className="mt-2 text-lg font-semibold sm:col-span-2">{t("onboarding.storeDetails")}</h2>
          <Field id="store_name" label={t("onboarding.storeName")} error={errors.store_name}>
            <TextInput id="store_name" value={f.store_name} onChange={set("store_name")} />
          </Field>
          <Field id="state" label={t("onboarding.state")}>
            <select id="state" value={f.state} onChange={set("state")} className="h-11 w-full rounded-lg border bg-white px-3 text-sm">
              {INDIAN_STATES.map((s) => (
                <option key={s.code} value={s.code}>{s.name}</option>
              ))}
            </select>
          </Field>
          <div className="sm:col-span-2">
            <Field id="business_address" label={t("onboarding.address")} error={errors.business_address}>
              <textarea id="business_address" rows={2} value={f.business_address} onChange={set("business_address")} className="w-full rounded-lg border px-3 py-2 text-sm" />
            </Field>
          </div>
          <Field id="gstin" label={`GSTIN (${t("common.optional")})`} hint={t("onboarding.gstinHint")} error={errors.gstin}>
            <TextInput id="gstin" value={f.gstin} onChange={set("gstin")} maxLength={15} className="uppercase" placeholder="29ABCDE1234F1Z5" />
          </Field>
          <div className="sm:col-span-2">
            <Field id="description" label={`${t("onboarding.description")} (${t("common.optional")})`}>
              <textarea id="description" rows={3} value={f.description} onChange={set("description")} className="w-full rounded-lg border px-3 py-2 text-sm" />
            </Field>
          </div>
          <button type="submit" disabled={busy} className="h-11 rounded-lg bg-brand text-sm font-semibold text-white hover:bg-brand/90 disabled:opacity-60 sm:col-span-2">
            {busy ? t("common.pleaseWait") : t("onboarding.submit")}
          </button>
          <p className="text-center text-sm text-muted-foreground sm:col-span-2">
            {t("auth.haveAccount")} <Link href="/login?redirect=/retailer" className="font-semibold text-brand">{t("nav.signIn")}</Link>
          </p>
        </form>
      </section>
    </div>
  );
}
