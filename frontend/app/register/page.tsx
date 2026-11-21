"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { BasketLoader } from "@/components/brand/basket-loader";
import { Field, TextInput } from "@/components/forms/field";
import { useAuth } from "@/lib/auth/auth-context";
import { postLoginDestination } from "@/lib/auth/roles";
import { errorMessage } from "@/lib/i18n/errors";
import { useI18n } from "@/lib/i18n/i18n-context";

function RegisterForm() {
  const router = useRouter();
  const requested = useSearchParams().get("redirect");
  const { register, isAuthenticated, user } = useAuth();
  const { t } = useI18n();
  const [f, setF] = useState({ full_name: "", email: "", phone: "", password: "", confirm: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (isAuthenticated && user) router.replace(postLoginDestination(user.role, requested));
  }, [isAuthenticated, user, requested, router]);

  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setF((p) => ({ ...p, [k]: e.target.value }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (f.full_name.trim().length < 2) errs.full_name = t("validation.name");
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(f.email.trim())) errs.email = t("validation.email");
    if (f.phone && !/^\+?[0-9]{10,13}$/.test(f.phone.replace(/\s/g, ""))) errs.phone = t("validation.phone");
    if (f.password.length < 8) errs.password = t("validation.password");
    if (f.password !== f.confirm) errs.confirm = t("validation.passwordMatch");
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setBusy(true);
    setFormError(null);
    try {
      const u = await register({
        full_name: f.full_name.trim(),
        email: f.email.trim(),
        phone: f.phone.trim() || null,
        password: f.password,
      });
      router.replace(postLoginDestination(u.role, requested));
    } catch (err) {
      setFormError(errorMessage(err, t));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="container-page flex min-h-[calc(100vh-12rem)] items-center justify-center py-10">
      <section className="w-full max-w-md rounded-2xl border bg-white p-6 shadow-sm sm:p-8">
        <h1 className="text-2xl font-bold">{t("auth.registerTitle")}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{t("auth.registerSubtitle")}</p>
        {formError && (
          <p role="alert" className="mt-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">{formError}</p>
        )}
        <form onSubmit={submit} className="mt-6 space-y-4" noValidate>
          <Field id="full_name" label={t("auth.fullName")} error={errors.full_name}>
            <TextInput id="full_name" autoComplete="name" value={f.full_name} onChange={set("full_name")} />
          </Field>
          <Field id="email" label={t("auth.email")} error={errors.email}>
            <TextInput id="email" type="email" autoComplete="email" value={f.email} onChange={set("email")} />
          </Field>
          <Field id="phone" label={`${t("auth.phone")} (${t("common.optional")})`} error={errors.phone}>
            <TextInput id="phone" type="tel" autoComplete="tel" value={f.phone} onChange={set("phone")} placeholder="+91 98xxxxxxxx" />
          </Field>
          <Field id="password" label={t("auth.password")} hint={t("validation.password")} error={errors.password}>
            <TextInput id="password" type="password" autoComplete="new-password" value={f.password} onChange={set("password")} />
          </Field>
          <Field id="confirm" label={t("auth.confirmPassword")} error={errors.confirm}>
            <TextInput id="confirm" type="password" autoComplete="new-password" value={f.confirm} onChange={set("confirm")} />
          </Field>
          <button type="submit" disabled={busy} className="h-11 w-full rounded-lg bg-brand text-sm font-semibold text-white hover:bg-brand/90 disabled:opacity-60">
            {busy ? t("common.pleaseWait") : t("auth.registerButton")}
          </button>
        </form>
        <p className="mt-6 text-center text-sm text-muted-foreground">
          {t("auth.haveAccount")} <Link href="/login" className="font-semibold text-brand">{t("nav.signIn")}</Link>
        </p>
        <p className="mt-2 text-center text-sm text-muted-foreground">
          {t("auth.sellerQuestion")} <Link href="/register/retailer" className="font-semibold text-brand-dark">{t("nav.sellOnBasket")}</Link>
        </p>
      </section>
    </div>
  );
}

export default function RegisterPage() {
  return (
    <Suspense fallback={<BasketLoader />}>
      <RegisterForm />
    </Suspense>
  );
}
