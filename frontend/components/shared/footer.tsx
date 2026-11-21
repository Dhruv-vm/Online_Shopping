"use client";

import Link from "next/link";
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
    <footer className="mt-16 bg-brand-dark text-white">
      <div className="container-page grid gap-10 py-12 md:grid-cols-[1.4fr_repeat(4,1fr)]">
        <div className="space-y-3">
          <BasketLogo inverted tagline={t("header.tagline")} />
          <p className="max-w-xs text-sm text-white/75">{t("footer.about")}</p>
          <p className="text-xs text-white/60">{t("footer.payments")}</p>
        </div>
        {COLUMNS.map((c) => (
          <div key={c.title}>
            <h3 className="mb-3 text-sm font-semibold text-brand-yellow">{t(c.title)}</h3>
            <ul className="space-y-2 text-sm text-white/80">
              {c.links.map((l) => (
                <li key={l.href}>
                  <Link href={l.href} className="hover:text-white hover:underline">
                    {t(l.key)}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="border-t border-white/10">
        <div className="container-page flex flex-col gap-2 py-4 text-xs text-white/60 sm:flex-row sm:items-center sm:justify-between">
          <span>{t("footer.copyright", { year: new Date().getFullYear() })}</span>
          <span>{t("footer.demoNotice")}</span>
        </div>
      </div>
    </footer>
  );
}
