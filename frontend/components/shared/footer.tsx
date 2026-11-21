"use client";

import Link from "next/link";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { usePathname } from "next/navigation";
import { BasketLogo } from "@/components/brand/logo";
import { useI18n } from "@/lib/i18n/i18n-context";

const COLUMNS: { title: string; links: { href: string; key: string }[] }[] = [
  {
    title: "footer.shop",
    links: [
      { href: "/products", key: "nav.catalogue" },
      { href: "/categories", key: "nav.categories" },
      { href: "/sale-stream", key: "nav.saleStream" },
      { href: "/community-buying", key: "nav.communityBuying" },
      { href: "/auctions", key: "nav.auctions" },
      { href: "/missions", key: "nav.missions" },
    ],
  },
  {
    title: "footer.account",
    links: [
      { href: "/account", key: "nav.account" },
      { href: "/orders", key: "nav.orders" },
      { href: "/account/price-alerts", key: "nav.priceAlerts" },
      { href: "/account/requests", key: "nav.myRequests" },
      { href: "/cart", key: "nav.cart" },
    ],
  },
  {
    title: "footer.sellers",
    links: [
      { href: "/register/retailer", key: "nav.sellOnBasket" },
      { href: "/login?redirect=/retailer", key: "footer.retailerLogin" },
      { href: "/retailers", key: "nav.retailers" },
    ],
  },
  {
    title: "footer.policies",
    links: [
      { href: "/policies/returns", key: "footer.returns" },
      { href: "/policies/shipping", key: "footer.shipping" },
      { href: "/policies/privacy", key: "footer.privacy" },
      { href: "/policies/terms", key: "footer.terms" },
    ],
  },
];

export function Footer() {
  const { t } = useI18n();
  const pathname = usePathname();
  if (pathname?.startsWith("/admin") || pathname?.startsWith("/retailer/")) return null;
  return (
    <footer className="relative mt-20 overflow-hidden bg-ink text-white">
      {/* Yellow corner arcs, as in the reference */}
      <span aria-hidden className="pointer-events-none absolute -bottom-20 -left-20 h-36 w-36 rounded-full border-[20px] border-brand-yellow" />
      <span aria-hidden className="pointer-events-none absolute -bottom-20 -right-16 h-32 w-32 rounded-full bg-brand-yellow" />
      <div className="container-page relative grid gap-10 pb-16 pt-14 md:grid-cols-2 lg:grid-cols-[1.35fr_repeat(4,1fr)_1.5fr]">
        <div className="space-y-4">
          <BasketLogo height={32} />
          <p className="text-sm font-semibold text-white">{t("footer.tagline")}</p>
          <p className="max-w-xs text-sm leading-relaxed text-white/60">{t("footer.about")}</p>
          <p className="flex items-center gap-2 text-xs text-white/55">
            <ShieldCheck className="h-4 w-4 text-brand-yellow" aria-hidden /> {t("footer.payments")}
          </p>
        </div>
        {COLUMNS.map((c) => (
          <nav key={c.title} aria-label={t(c.title)}>
            <h3 className="mb-4 text-sm font-bold text-white">{t(c.title)}</h3>
            <ul className="space-y-2.5 text-sm text-white/65">
              {c.links.map((l) => (
                <li key={l.href}>
                  <Link href={l.href} className="transition-colors duration-base hover:text-brand-yellow">
                    {t(l.key)}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        ))}
        <div className="space-y-3">
          <h3 className="text-sm font-bold text-white">{t("footer.stayInLoop")}</h3>
          <p className="text-sm text-white/60">{t("footer.stayInLoopBody")}</p>
          <Link
            href="/account/price-alerts"
            className="press group inline-flex h-11 items-center gap-2 rounded-full bg-brand-yellow pl-5 pr-2 text-sm font-semibold text-ink hover:bg-brand-yellow-dark"
          >
            {t("nav.priceAlerts")}
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-ink text-brand-yellow transition-transform duration-base ease-out group-hover:translate-x-0.5">
              <ArrowRight className="h-4 w-4" />
            </span>
          </Link>
        </div>
      </div>
      <div className="relative border-t border-white/10">
        <div className="container-page flex flex-col gap-3 py-5 text-xs text-white/55 sm:flex-row sm:items-center sm:justify-between sm:!pl-20 sm:!pr-24">
          <span>{t("footer.copyright", { year: new Date().getFullYear() })}</span>
          <span className="hidden md:inline">{t("footer.demoNotice")}</span>
          <span className="flex gap-4">
            <Link href="/policies/privacy" className="hover:text-white">{t("footer.privacy")}</Link>
            <Link href="/policies/terms" className="hover:text-white">{t("footer.terms")}</Link>
          </span>
        </div>
      </div>
    </footer>
  );
}
