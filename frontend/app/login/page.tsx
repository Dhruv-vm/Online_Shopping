"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Eye, EyeOff, Lock, Mail, ShieldCheck, Store, User as UserIcon } from "lucide-react";
import { BasketLoader } from "@/components/brand/basket-loader";
import { useAuth } from "@/lib/auth/auth-context";
import { postLoginDestination } from "@/lib/auth/roles";
import { errorMessage } from "@/lib/i18n/errors";
import { useI18n } from "@/lib/i18n/i18n-context";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const requested = params.get("redirect");
  const expired = params.get("expired") === "1";
  const { login, isAuthenticated, user, isLoading } = useAuth();
  const { t } = useI18n();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Already signed in: go where the verified role belongs.
  useEffect(() => {
    if (!isLoading && isAuthenticated && user) {
      router.replace(postLoginDestination(user.role, requested));
    }
  }, [isLoading, isAuthenticated, user, requested, router]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!email.trim() || !password) {
      setError(t("auth.fillBoth"));
      return;
    }
    setBusy(true);
    try {
      // The role comes from the backend response, never from this form.
      const u = await login(email.trim(), password);
      router.replace(postLoginDestination(u.role, requested));
    } catch (err) {
      setError(errorMessage(err, t));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="container-page grid min-h-[calc(100vh-12rem)] items-center gap-10 py-10 lg:grid-cols-2">
      <section className="hidden space-y-6 lg:block">
        <h1 className="text-4xl font-bold leading-tight text-charcoal">{t("auth.welcomeTitle")}</h1>
        <p className="max-w-md text-muted-foreground">{t("auth.welcomeBody")}</p>
        <ul className="space-y-4">
          {[
            { icon: UserIcon, k: "auth.roleCustomer" },
            { icon: Store, k: "auth.roleRetailer" },
            { icon: ShieldCheck, k: "auth.roleAdmin" },
          ].map(({ icon: Icon, k }) => (
            <li key={k} className="flex items-start gap-3">
              <span className="mt-0.5 flex h-9 w-9 items-center justify-center rounded-lg bg-brand-light text-brand-dark">
                <Icon className="h-5 w-5" />
              </span>
              <span>
                <span className="block font-semibold">{t(`${k}.title`)}</span>
                <span className="block text-sm text-muted-foreground">{t(`${k}.body`)}</span>
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section className="mx-auto w-full max-w-md rounded-2xl border bg-white p-6 shadow-sm sm:p-8">
        <h2 className="text-2xl font-bold">{t("auth.signInTitle")}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{t("auth.signInSubtitle")}</p>
        {expired && (
          <p role="status" className="mt-4 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
            {t("auth.sessionExpired")}
          </p>
        )}
        {error && (
          <p role="alert" className="mt-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
            {error}
          </p>
        )}
        <form onSubmit={submit} className="mt-6 space-y-4" noValidate>
          <div>
            <label htmlFor="email" className="text-sm font-medium">{t("auth.email")}</label>
            <div className="relative mt-1">
              <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="h-11 w-full rounded-lg border pl-9 pr-3 text-sm focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/30"
              />
            </div>
          </div>
          <div>
            <label htmlFor="password" className="text-sm font-medium">{t("auth.password")}</label>
            <div className="relative mt-1">
              <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                id="password"
                type={show ? "text" : "password"}
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="h-11 w-full rounded-lg border pl-9 pr-10 text-sm focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/30"
              />
              <button
                type="button"
                onClick={() => setShow((s) => !s)}
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-muted-foreground"
                aria-label={show ? t("auth.hidePassword") : t("auth.showPassword")}
              >
                {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>
          <button
            type="submit"
            disabled={busy}
            className="h-11 w-full rounded-lg bg-brand text-sm font-semibold text-white transition hover:bg-brand/90 disabled:opacity-60"
          >
            {busy ? t("auth.signingIn") : t("auth.signInButton")}
          </button>
        </form>
        <p className="mt-6 text-center text-sm text-muted-foreground">
          {t("auth.noAccount")}{" "}
          <Link href="/register" className="font-semibold text-brand">{t("auth.createAccount")}</Link>
        </p>
        <p className="mt-2 text-center text-sm text-muted-foreground">
          {t("auth.sellerQuestion")}{" "}
          <Link href="/register/retailer" className="font-semibold text-brand-dark">{t("nav.sellOnBasket")}</Link>
        </p>
        <p className="mt-6 border-t pt-4 text-xs text-muted-foreground">{t("auth.oneLoginNote")}</p>
      </section>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<BasketLoader />}>
      <LoginForm />
    </Suspense>
  );
}
