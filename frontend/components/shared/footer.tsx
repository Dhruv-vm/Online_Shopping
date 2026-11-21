"use client";

import Link from "next/link";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { usePathname } from "next/navigation";
import { BasketLogo } from "@/components/brand/logo";
import { useI18n } from "@/lib/i18n/i18n-context";

// Only links with a real destination in the app. (No FAQ, careers, social or
// cookie pages exist yet, so none are linked.)
const COLUMNS: { title: string; links: { href: string; key: string }[] }[] = [
  {
    title: "footer.shop",
    links: [
      { href: "/categories", key: "nav.categories" },
      { href: "/products?sort_by=newest", key: "nav.newArrivals" },
      { href: "/#the-basket-edit", key: "nav.collections" },
      { href: "/sale-stream", key: "nav.deals" },
      { href: "/community-buying", key: "nav.communityBuying" },
      { href: "/auctions", key: "nav.auctions" },
    ],
  },
  {
    title: "footer.help",
    links: [
      { href: "/orders", key: "footer.trackOrder" },
      { href: "/policies/returns", key: "footer.returns" },
      { href: "/policies/shipping", key: "footer.shipping" },
      { href: "/account", key: "nav.account" },
    ],
  },
  {
    title: "footer.aboutTitle",
    links: [
      { href: "/retailers", key: "nav.retailers" },
      { href: "/register/retailer", key: "footer.partner" },
      { href: "/login?redirect=/retailer", key: "footer.retailerLogin" },
      { href: "/missions", key: "nav.missions" },
    ],
  },
];

export function Footer() {
  const { t } = useI18n();
  const pathname = usePathname();
  if (pathname?.startsWith("/admin") || pathname?.startsWith("/retailer/")) return null;
  return (
    <footer className="relative mt-20 overflow-hidden bg-ink text-white">
      {/* Yellow corner swooshes, as in the reference */}
      <svg aria-hidden className="pointer-events-none absolute bottom-0 left-0 h-28 w-44 sm:h-36 sm:w-60" viewBox="0 0 240 144" preserveAspectRatio="none">
        <path d="M0 40 C 60 70, 110 110, 140 144 L0 144 Z" fill="#FDCD1E" />
      </svg>
      <svg aria-hidden className="pointer-events-none absolute bottom-0 right-0 h-28 w-40 sm:h-40 sm:w-56" viewBox="0 0 224 160" preserveAspectRatio="none">
        <path d="M224 0 C 190 70, 130 130, 70 160 L224 160 Z" fill="#FDCD1E" />
      </svg>

      <div className="container-page relative grid grid-cols-2 gap-x-6 gap-y-10 pb-12 pt-14 sm:grid-cols-3 lg:grid-cols-[1.3fr_1fr_1fr_1fr_1.5fr] lg:gap-8">
        <div className="col-span-2 space-y-4 sm:col-span-3 lg:col-span-1">
          <BasketLogo height={34} />
          <p className="text-[15px] font-semibold text-white">{t("footer.tagline")}</p>
          <p className="flex max-w-xs items-start gap-2 text-xs leading-relaxed text-white/55">
            <ShieldCheck className="mt-px h-4 w-4 shrink-0 text-brand-yellow" aria-hidden /> {t("footer.payments")}
          </p>
        </div>
        {COLUMNS.map((c) => (
          <nav key={c.title} aria-label={t(c.title)}>
            <h3 className="mb-4 text-[15px] font-bold text-white">{t(c.title)}</h3>
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
        <div className="col-span-2 sm:col-span-3 lg:col-span-1">
          <h3 className="text-[15px] font-bold text-white">{t("footer.stayInLoop")}</h3>
          <p className="mt-2 text-sm text-white/60">{t("footer.stayInLoopBody")}</p>
          {/* Price-drop alerts are the existing opt-in for updates (there is no newsletter list). */}
          <Link
            href="/account/price-alerts"
            className="group mt-4 flex h-12 max-w-sm items-center justify-between rounded-xl bg-white/[0.06] pl-4 pr-1.5 text-sm text-white/80 ring-1 ring-white/15 transition-colors duration-base hover:bg-white/[0.1] hover:text-white"
          >
            {t("footer.alertsCta")}
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-yellow text-ink transition-transform duration-base ease-out group-hover:translate-x-0.5">
              <ArrowRight className="h-4 w-4 rtl:rotate-180" />
            </span>
          </Link>
        </div>
      </div>

      <div className="container-page relative">
        <div className="flex flex-col gap-3 border-t border-white/10 pb-16 pt-5 text-xs text-white/55 sm:pb-6 md:flex-row md:items-center md:justify-between md:pl-32">
          <span>{t("footer.copyright", { year: new Date().getFullYear() })}</span>
          <span className="hidden lg:inline">{t("footer.demoNotice")}</span>
          <span className="flex items-center gap-3 md:pr-28">
            <Link href="/policies/privacy" className="hover:text-white">{t("footer.privacyPolicy")}</Link>
            <span aria-hidden className="text-white/25">|</span>
            <Link href="/policies/terms" className="hover:text-white">{t("footer.termsService")}</Link>
          </span>
        </div>
      </div>
    </footer>
  );
}
