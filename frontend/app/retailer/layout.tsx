"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  AlertTriangle,
  ArrowLeft,
  BarChart3,
  ClipboardCheck,
  ExternalLink,
  FileSearch,
  Gavel,
  Handshake,
  IndianRupee,
  LayoutDashboard,
  Layers,
  Package,
  PlusCircle,
  Settings,
  ShoppingCart,
  Store,
  Tag,
  TrendingUp,
  Users,
} from "lucide-react";
import { BasketLoader } from "@/components/brand/basket-loader";
import { apiClient } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/auth-context";
import { useI18n } from "@/lib/i18n/i18n-context";
import type { RetailerProfile } from "@/types";

type Item = { href: string; key: string; icon: typeof Store; verifiedOnly?: boolean };

const GROUPS: { key: string; items: Item[] }[] = [
  { key: "retailer.group.desk", items: [{ href: "/retailer", key: "retailer.nav.overview", icon: LayoutDashboard }] },
  {
    key: "retailer.group.catalogue",
    items: [
      { href: "/retailer/listings", key: "retailer.nav.products", icon: Layers },
      { href: "/retailer/listings/new", key: "retailer.nav.addProduct", icon: PlusCircle, verifiedOnly: true },
      { href: "/retailer/inventory", key: "retailer.nav.inventory", icon: Package },
    ],
  },
  {
    key: "retailer.group.sales",
    items: [
      { href: "/retailer/orders", key: "retailer.nav.orders", icon: ShoppingCart },
      { href: "/retailer/offers", key: "retailer.nav.offers", icon: Tag },
      { href: "/retailer/analytics", key: "retailer.nav.analytics", icon: BarChart3 },
      { href: "/retailer/price-insights", key: "retailer.nav.priceInsights", icon: TrendingUp },
    ],
  },
  {
    key: "retailer.group.marketplace",
    items: [
      { href: "/retailer/demand-gaps", key: "retailer.nav.demandGaps", icon: FileSearch },
      { href: "/retailer/exchange", key: "retailer.nav.rfqBids", icon: IndianRupee },
      { href: "/retailer/auctions", key: "retailer.nav.auctions", icon: Gavel },
      { href: "/retailer/community-buying", key: "retailer.nav.groupBuys", icon: Users },
      { href: "/retailer/negotiation", key: "retailer.nav.negotiation", icon: Handshake },
    ],
  },
  {
    key: "retailer.group.store",
    items: [
      { href: "/retailer/onboarding", key: "retailer.nav.verification", icon: ClipboardCheck },
      { href: "/retailer/profile", key: "retailer.nav.profile", icon: Store },
      { href: "/retailer/settings", key: "retailer.nav.settings", icon: Settings },
    ],
  },
];

/** Pages a not-yet-verified store may use (complete profile, submit documents). */
const PRE_VERIFICATION = ["/retailer", "/retailer/onboarding", "/retailer/profile", "/retailer/settings"];

export default function RetailerLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname() ?? "/retailer";
  const { user, isAuthenticated, isLoading } = useAuth();
  const { t } = useI18n();
  const [profile, setProfile] = useState<RetailerProfile | null>(null);
  const [profileError, setProfileError] = useState(false);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) router.replace(`/login?redirect=${encodeURIComponent(pathname)}`);
  }, [isLoading, isAuthenticated, pathname, router]);

  useEffect(() => {
    if (user?.role !== "retailer") return;
    let alive = true;
    apiClient
      .getRetailerProfile()
      .then((p) => alive && setProfile(p))
      .catch(() => alive && setProfileError(true));
    return () => {
      alive = false;
    };
  }, [user?.role, pathname]);

  if (isLoading || (isAuthenticated && user?.role === "retailer" && !profile && !profileError)) {
    return <BasketLoader label={t("retailer.loading")} className="min-h-[50vh]" />;
  }
  if (!isAuthenticated) return null;

  if (user?.role !== "retailer") {
    return (
      <div className="container-page max-w-xl py-16 text-center">
        <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-yellow/30 text-charcoal">
          <Store className="h-8 w-8" />
        </div>
        <h1 className="text-2xl font-bold">{t("retailer.accessRequired.title")}</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          {t("retailer.accessRequired.body", { email: user?.email ?? "", role: t(`role.${user?.role ?? "customer"}`) })}
        </p>
        <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
          <Link href="/register/retailer" className="rounded-lg bg-brand px-4 py-2.5 text-sm font-semibold text-white">{t("nav.sellOnBasket")}</Link>
          <Link href="/" className="inline-flex items-center justify-center gap-2 rounded-lg border px-4 py-2.5 text-sm font-semibold">
            <ArrowLeft className="h-4 w-4" /> {t("common.backToStore")}
          </Link>
        </div>
      </div>
    );
  }

  const status = profile?.verification_status ?? "PENDING";
  const verified = status === "VERIFIED" && profile?.is_active !== false;
  const restricted = !verified && !PRE_VERIFICATION.includes(pathname);

  return (
    <div className="min-h-screen bg-surface">
      <div className="bg-brand-dark text-white">
        <div className="container-page flex flex-wrap items-center justify-between gap-2 py-2 text-xs">
          <div className="flex items-center gap-2">
            <Store className="h-4 w-4 text-brand-yellow" />
            <span className="font-semibold tracking-wide">{profile?.name ?? t("retailer.banner.portal")}</span>
            <span className="rounded bg-white/10 px-1.5 py-0.5 text-[10px]">{t("retailer.banner.center")}</span>
          </div>
          <div className="flex items-center gap-4 text-white/80">
            {verified && (
              <span>
                {t("retailer.banner.storeStatus")}{" "}
                <strong className={profile?.is_open ? "text-brand-yellow" : "text-white"}>
                  {profile?.is_open ? t("retailer.banner.open") : t("retailer.banner.closed")}
                </strong>
              </span>
            )}
            {profile?.id && verified && (
              <Link href={`/products?retailer_id=${profile.id}`} className="inline-flex items-center gap-1 underline">
                {t("retailer.banner.viewStore")} <ExternalLink className="h-3 w-3" />
              </Link>
            )}
            <Link href="/" className="underline">{t("common.backToStore")}</Link>
          </div>
        </div>
      </div>

      {!verified && (
        <div className={`${status === "REJECTED" || status === "SUSPENDED" ? "bg-red-50 text-red-900 border-red-200" : "bg-amber-50 text-amber-900 border-amber-200"} border-b`}>
          <div className="container-page flex flex-wrap items-center gap-2 py-2.5 text-sm">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span className="font-semibold">{t(`retailer.status.${status}.title`)}</span>
            <span>{t(`retailer.status.${status}.body`)}</span>
            <Link href="/retailer/onboarding" className="ml-auto font-semibold underline">{t("retailer.status.cta")}</Link>
          </div>
        </div>
      )}

      <div className="container-page grid gap-6 py-6 lg:grid-cols-[15rem_1fr]">
        <aside className="lg:sticky lg:top-24 lg:self-start">
          <nav aria-label={t("retailer.banner.portal")} className="no-scrollbar flex gap-1 overflow-x-auto rounded-xl border bg-white p-2 lg:block lg:space-y-4 lg:overflow-visible lg:p-3">
            {GROUPS.map((g) => (
              <div key={g.key} className="flex gap-1 lg:block lg:space-y-0.5">
                <p className="hidden px-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground lg:block">{t(g.key)}</p>
                {g.items.map(({ href, key, icon: Icon, verifiedOnly }) => {
                  const active = href === "/retailer" ? pathname === "/retailer" : pathname.startsWith(href);
                  const disabled = (verifiedOnly || !PRE_VERIFICATION.includes(href)) && !verified;
                  return (
                    <Link
                      key={href}
                      href={href}
                      aria-current={active ? "page" : undefined}
                      className={`flex shrink-0 items-center gap-2.5 whitespace-nowrap rounded-md px-2.5 py-2 text-sm ${
                        active ? "bg-brand-light font-semibold text-brand-dark" : "text-charcoal/80 hover:bg-muted"
                      } ${disabled ? "opacity-50" : ""}`}
                    >
                      <Icon className="h-4 w-4" /> {t(key)}
                    </Link>
                  );
                })}
              </div>
            ))}
          </nav>
        </aside>
        <section className="min-w-0">
          {restricted ? (
            <div className="rounded-xl border bg-white p-8 text-center">
              <ClipboardCheck className="mx-auto h-10 w-10 text-brand" />
              <h1 className="mt-3 text-xl font-bold">{t("retailer.restricted.title")}</h1>
              <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">{t("retailer.restricted.body")}</p>
              <Link href="/retailer/onboarding" className="mt-5 inline-block rounded-lg bg-brand px-4 py-2.5 text-sm font-semibold text-white">
                {t("retailer.status.cta")}
              </Link>
            </div>
          ) : (
            children
          )}
        </section>
      </div>
    </div>
  );
}
