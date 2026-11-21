"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Activity,
  ArrowLeft,
  BarChart3,
  FileClock,
  FileSearch,
  Gavel,
  IndianRupee,
  LayoutGrid,
  Package,
  ShieldAlert,
  ShieldCheck,
  Store,
  Tag,
  TrendingUp,
  Users,
  UsersRound,
} from "lucide-react";
import { BasketLoader } from "@/components/brand/basket-loader";
import { useAuth } from "@/lib/auth/auth-context";
import { useI18n } from "@/lib/i18n/i18n-context";

const NAV = [
  { href: "/admin", key: "admin.nav.overview", icon: BarChart3 },
  { href: "/admin/retailers", key: "admin.nav.retailers", icon: Store },
  { href: "/admin/catalogue", key: "admin.nav.catalogue", icon: LayoutGrid },
  { href: "/admin/deals", key: "admin.nav.deals", icon: Tag },
  { href: "/admin/demand", key: "admin.nav.demand", icon: FileSearch },
  { href: "/admin/rfqs", key: "admin.nav.rfqs", icon: IndianRupee },
  { href: "/admin/group-buying", key: "admin.nav.groupBuying", icon: UsersRound },
  { href: "/admin/auctions", key: "admin.nav.auctions", icon: Gavel },
  { href: "/admin/price-intelligence", key: "admin.nav.priceIntel", icon: TrendingUp },
  { href: "/admin/users", key: "admin.nav.users", icon: Users },
  { href: "/admin/orders", key: "admin.nav.orders", icon: Package },
  { href: "/admin/audit-logs", key: "admin.nav.audit", icon: FileClock },
  { href: "/admin/settings", key: "admin.nav.settings", icon: Activity },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname() ?? "/admin";
  const { user, isAuthenticated, isLoading } = useAuth();
  const { t } = useI18n();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) router.replace(`/login?redirect=${encodeURIComponent(pathname)}`);
  }, [isLoading, isAuthenticated, pathname, router]);

  if (isLoading) return <BasketLoader label={t("admin.loading")} className="min-h-[50vh]" />;
  if (!isAuthenticated) return null;
  if (user?.role !== "admin") {
    return (
      <div className="container-page max-w-xl py-16 text-center">
        <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-red-100 text-red-700">
          <ShieldAlert className="h-8 w-8" />
        </div>
        <h1 className="text-2xl font-bold">{t("admin.denied.title")}</h1>
        <p className="mt-2 text-sm text-muted-foreground">{t("admin.denied.body", { email: user?.email ?? "" })}</p>
        <Link href="/" className="mt-6 inline-flex items-center gap-2 rounded-lg border px-4 py-2.5 text-sm font-semibold">
          <ArrowLeft className="h-4 w-4" /> {t("common.backToStore")}
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-surface">
      <div className="bg-charcoal text-white">
        <div className="container-page flex flex-wrap items-center justify-between gap-2 py-2 text-xs">
          <span className="flex items-center gap-2 font-semibold tracking-wide">
            <ShieldCheck className="h-4 w-4 text-brand-yellow" /> {t("admin.banner.title")}
          </span>
          <span className="flex items-center gap-4 text-white/75">
            <span>{t("admin.banner.operator")}: <strong className="text-white">{user.full_name}</strong></span>
            <Link href="/" className="underline">{t("common.backToStore")}</Link>
          </span>
        </div>
      </div>
      <div className="container-page grid gap-6 py-6 lg:grid-cols-[15rem_1fr]">
        <aside className="lg:sticky lg:top-24 lg:self-start">
          <nav aria-label={t("admin.banner.title")} className="no-scrollbar flex gap-1 overflow-x-auto rounded-xl border bg-white p-2 lg:block lg:space-y-0.5 lg:p-3">
            {NAV.map(({ href, key, icon: Icon }) => {
              const active = href === "/admin" ? pathname === "/admin" : pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={`flex shrink-0 items-center gap-2.5 whitespace-nowrap rounded-md px-2.5 py-2 text-sm ${active ? "bg-brand-light font-semibold text-brand-dark" : "text-charcoal/80 hover:bg-muted"}`}
                >
                  <Icon className="h-4 w-4" /> {t(key)}
                </Link>
              );
            })}
          </nav>
        </aside>
        <section className="min-w-0">{children}</section>
      </div>
    </div>
  );
}
