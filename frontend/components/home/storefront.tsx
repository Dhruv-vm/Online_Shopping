"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import { ArrowLeft, ArrowRight, Leaf, Package, ShieldCheck, Star, Tag, Truck } from "lucide-react";
import { ProductCard } from "@/components/catalogue/product-card";
import { ProductImage } from "@/components/catalogue/product-image";
import { Reveal } from "@/components/motion/reveal";
import { CampaignBanner } from "@/components/home/promo-banner";
import { useI18n } from "@/lib/i18n/i18n-context";
import type { SaleStreamItem } from "@/lib/api/phase3";
import type { Category, ProductSummary, Retailer } from "@/types";

/* ------------------------------------------------------------------ helpers */

export function discountOf(p: ProductSummary) {
  return p.is_in_stock && p.original_price_paise && p.original_price_paise > p.min_price_paise && p.min_price_paise > 0
    ? Math.round(((p.original_price_paise - p.min_price_paise) / p.original_price_paise) * 100)
    : 0;
}

/** First product with a photo for each category slug. */
export function imageByCategory(products: ProductSummary[]) {
  const map = new Map<string, ProductSummary>();
  for (const p of products) if (p.primary_image && !map.has(p.category_slug)) map.set(p.category_slug, p);
  return map;
}

/** Products whose name/category match each pattern, one per pattern, never repeated. */
function pickProducts(products: ProductSummary[], patterns: RegExp[]): (ProductSummary | undefined)[] {
  const used = new Set<string>();
  const withImg = products.filter((p) => p.primary_image);
  const picks = patterns.map((re) => {
    const p = withImg.find((x) => !used.has(x.id) && re.test(`${x.name} ${x.category_slug}`));
    if (p) used.add(p.id);
    return p;
  });
  // Fill gaps with other photographed products so the composition is never empty.
  return picks.map((p) => {
    if (p) return p;
    const f = withImg.find((x) => !used.has(x.id));
    if (f) used.add(f.id);
    return f;
  });
}

/** Translate a string with a {pct}-style slot rendered as a highlighted node. */
function highlightSlot(text: string, render: (suffix: string) => ReactNode) {
  const [before, rest = ""] = text.split("\u0000");
  // Keep a directly following "%" inside the highlight ("60%" reads as one figure).
  const suffix = rest.startsWith("%") ? "%" : "";
  return (
    <>
      {before}
      {render(suffix)}
      {rest.slice(suffix.length)}
    </>
  );
}

export function SectionHead({
  id,
  title,
  subtitle,
  href,
  linkLabel,
  accent = false,
  actions,
}: {
  id: string;
  title: string;
  subtitle?: string;
  href?: string;
  linkLabel?: string;
  accent?: boolean;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 id={`${id}-title`} className="flex items-center gap-4 text-[1.6rem] font-extrabold tracking-[-0.02em] text-ink sm:text-[1.85rem]">
          {title}
          {accent && <span aria-hidden className="mt-1 hidden h-[3px] w-10 rounded-full bg-brand-yellow sm:block" />}
        </h2>
        {subtitle && <p className="mt-1 text-sm text-ink/60">{subtitle}</p>}
      </div>
      {actions}
      {href && linkLabel && (
        <Link
          href={href}
          className="group inline-flex items-center gap-1.5 border-b-2 border-brand-green-logo/25 pb-0.5 text-sm font-bold text-brand-green-logo transition-colors duration-base hover:border-brand-green-logo"
        >
          {linkLabel}
          <ArrowRight className="h-4 w-4 transition-transform duration-base ease-out group-hover:translate-x-1" />
        </Link>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ hero */

function Laurel({ flip = false }: { flip?: boolean }) {
  return (
    <svg viewBox="0 0 20 40" aria-hidden className={`h-9 w-[18px] text-brand-yellow ${flip ? "-scale-x-100" : ""}`} fill="currentColor">
      <path d="M15 38c-6-4-9-11-8-19 .2-2 .6-4 1.3-6l1.2.4c-.6 1.9-1 3.8-1.2 5.7-.9 7.4 1.9 13.9 7.4 17.7z" />
      <ellipse cx="6.2" cy="30" rx="2.2" ry="4.2" transform="rotate(-40 6.2 30)" />
      <ellipse cx="4.2" cy="22.5" rx="2" ry="4" transform="rotate(-15 4.2 22.5)" />
      <ellipse cx="4.6" cy="15" rx="1.9" ry="3.8" transform="rotate(10 4.6 15)" />
      <ellipse cx="7.2" cy="8.2" rx="1.7" ry="3.4" transform="rotate(30 7.2 8.2)" />
      <ellipse cx="11.8" cy="33.5" rx="2" ry="3.6" transform="rotate(-80 11.8 33.5)" />
    </svg>
  );
}

function LeafSpray({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 160 220" aria-hidden className={className}>
      <path d="M120 220 C 112 160, 96 110, 60 60" stroke="#2F7A3B" strokeWidth="3" fill="none" />
      <path d="M60 60 C 30 50, 12 22, 18 2 C 48 10, 70 32, 60 60 Z" fill="#3E9443" />
      <path d="M86 108 C 52 112, 24 92, 14 66 C 46 62, 76 78, 86 108 Z" fill="#2F7A3B" />
      <path d="M78 92 C 86 60, 112 40, 140 36 C 140 66, 112 92, 78 92 Z" fill="#4FA84D" />
      <path d="M104 160 C 70 170, 40 158, 24 134 C 56 124, 90 132, 104 160 Z" fill="#3E9443" />
      <path d="M100 140 C 110 108, 136 92, 158 92 C 156 122, 132 142, 100 140 Z" fill="#2F7A3B" />
    </svg>
  );
}

function Arch({ p, className, delay, rounded = "arch", eager = false }: { p?: ProductSummary; className: string; delay: number; rounded?: "arch" | "circle"; eager?: boolean }) {
  const shape = rounded === "circle" ? "rounded-full" : "rounded-t-[999px] rounded-b-[1.4rem]";
  return (
    <Reveal delay={delay} className={`absolute ${className}`}>
      {p ? (
        <Link href={`/products/${p.slug}`} aria-label={p.name} className={`group block h-full w-full overflow-hidden bg-white shadow-card-hover ring-[5px] ring-white ${shape}`}>
          <ProductImage src={p.primary_image} alt={p.name} eager={eager} sizes="(min-width: 1024px) 16vw, 30vw" className="transition-transform duration-slow ease-out group-hover:scale-[1.07]" />
        </Link>
      ) : (
        <span className={`block h-full w-full animate-pulse bg-cream ring-[5px] ring-white ${shape}`} />
      )}
    </Reveal>
  );
}

export function StorefrontHero({
  products,
  retailers,
  stats,
}: {
  products: ProductSummary[] | null;
  retailers: Retailer[] | null;
  stats: { products: number; stores: number } | null;
}) {
  const { t, number } = useI18n();
  const [headphones, phone, shoes, beauty, gadget] = products
    ? pickProducts(products, [/headphone|airpods|earbud|audio/i, /iphone|galaxy|smartphone|phone|mobile/i, /shoe|sneaker|boot|footwear/i, /cream|perfume|serum|beauty/i, /watch|macbook|laptop/i])
    : [];
  const rated = (retailers ?? []).filter((r) => r.rating > 0);
  const avgRating = rated.length ? rated.reduce((s, r) => s + r.rating, 0) / rated.length : 0;
  const faces = (retailers ?? []).filter((r) => r.logo_url).slice(0, 4);

  return (
    <section className="relative overflow-hidden" aria-labelledby="hero-title">
      <div className="container-page grid items-center gap-8 pb-8 pt-8 lg:grid-cols-[1fr_1.05fr] lg:gap-4 lg:pb-10 lg:pt-10">
        <div className="relative z-10">
          <Reveal>
            <p className="flex items-center gap-3 text-[11px] font-bold uppercase tracking-[0.2em] text-ink/80 sm:text-xs">
              {t("home.v2.eyebrow")}
              <span aria-hidden className="h-[3px] w-9 rounded-full bg-brand-yellow" />
            </p>
          </Reveal>
          <Reveal delay={80}>
            <h1 id="hero-title" className="mt-4 text-[2.7rem] font-extrabold leading-[1.04] tracking-[-0.035em] text-ink sm:text-6xl xl:text-[4.4rem]">
              {t("home.v2.title1")}
              <br />
              {t("home.v2.title2")}{" "}
              <span className="relative inline-block whitespace-nowrap px-[0.18em]">
                <span aria-hidden className="absolute inset-x-0 bottom-[0.04em] top-[0.14em] -z-10 -skew-x-6 rounded-[0.32em] bg-brand-yellow" />
                {t("home.v2.title3")}
              </span>
            </h1>
          </Reveal>
          <Reveal delay={160}>
            <p className="mt-5 max-w-[26rem] text-[15px] leading-relaxed text-ink/75 sm:text-base">{t("home.v2.subtitle")}</p>
          </Reveal>
          <Reveal delay={240} className="mt-7 flex items-center gap-3">
            <Link href="/products" className="press group inline-flex h-12 flex-1 items-center justify-center gap-2 whitespace-nowrap rounded-full bg-brand-yellow pl-5 pr-4 sm:flex-none sm:pl-6 sm:pr-5 text-[15px] font-bold text-ink shadow-[0_8px_20px_-10px_rgba(232,184,0,0.9)] hover:bg-brand-yellow-dark">
              {t("home.v2.cta")}
              <ArrowRight className="h-4 w-4 transition-transform duration-base ease-out group-hover:translate-x-1" />
            </Link>
            <Link href="/sale-stream" className="press inline-flex h-12 flex-1 items-center justify-center gap-2 whitespace-nowrap rounded-full bg-white px-5 sm:flex-none sm:px-6 text-[15px] font-bold text-ink ring-1 ring-ink/15 hover:ring-ink/40">
              <Tag className="h-4 w-4" aria-hidden />
              {t("home.v2.viewDeals")}
            </Link>
          </Reveal>
          {(stats || avgRating > 0) && (
            <Reveal delay={320}>
              <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-4">
                {stats && (
                  <Link href="/retailers" className="group flex items-center gap-3">
                    {faces.length > 0 && (
                      <span className="flex -space-x-2.5">
                        {faces.map((r) => (
                          <span key={r.id} className="relative block h-9 w-9 overflow-hidden rounded-full bg-cream ring-2 ring-surface">
                            <ProductImage src={r.logo_url} alt={r.name} sizes="36px" />
                          </span>
                        ))}
                      </span>
                    )}
                    <span className="text-[13px] font-bold text-ink group-hover:underline">{t("home.v2.trustStores", { n: number(stats.stores) })}</span>
                  </Link>
                )}
                {stats && avgRating > 0 && <span aria-hidden className="hidden h-9 w-px bg-ink/15 sm:block" />}
                {avgRating > 0 && (
                  <span className="flex items-center gap-1">
                    <Laurel />
                    <span className="text-center leading-none">
                      <span className="flex items-center justify-center gap-0.5 text-[15px] font-extrabold text-ink">
                        {avgRating.toFixed(1)}
                        <Star className="h-3.5 w-3.5 fill-ink" aria-hidden />
                      </span>
                      <span className="mt-1 block text-[10.5px] font-semibold text-ink/60">{t("home.v2.storeRating")}</span>
                    </span>
                    <Laurel flip />
                  </span>
                )}
              </div>
            </Reveal>
          )}
        </div>

        {/* Editorial product composition: real catalogue products on a podium */}
        <div className="relative mx-auto aspect-[1.18] w-full max-w-[24rem] sm:max-w-[34rem] lg:mr-[-2rem] lg:max-w-[40rem]">
          <Reveal className="absolute inset-0" delay={40}>
            <svg viewBox="0 0 600 510" aria-hidden className="h-full w-full">
              <defs>
                <radialGradient id="hero-glow" cx="55%" cy="45%" r="55%">
                  <stop offset="0" stopColor="#FFF3C4" />
                  <stop offset="1" stopColor="#FAF8F4" stopOpacity="0" />
                </radialGradient>
              </defs>
              <ellipse cx="320" cy="250" rx="300" ry="240" fill="url(#hero-glow)" />
              <path d="M10 470 C 120 300, 330 120, 590 70" stroke="#FDCD1E" strokeWidth="46" strokeLinecap="round" fill="none" />
              <path d="M60 500 C 190 340, 380 170, 600 130" stroke="#FDE58A" strokeWidth="10" strokeLinecap="round" fill="none" opacity="0.8" />
            </svg>
          </Reveal>
          {/* Podium */}
          <span aria-hidden className="absolute bottom-[3%] left-[34%] right-[-4%] h-[22%] rounded-t-2xl bg-gradient-to-b from-white to-[#F1EEE8] shadow-[0_24px_40px_-24px_rgba(8,8,8,0.35)]" />
          <span aria-hidden className="absolute bottom-0 left-[8%] right-[30%] h-[13%] rounded-t-2xl bg-gradient-to-b from-white to-[#EFEBE4] shadow-[0_24px_40px_-24px_rgba(8,8,8,0.35)]" />

          <Arch p={headphones} className="bottom-[12%] left-[6%] h-[50%] w-[30%] z-[2]" delay={120} eager />
          <Arch p={phone} className="bottom-[24%] left-[37%] h-[64%] w-[27%] z-[1]" delay={200} eager />
          <Arch p={shoes} className="bottom-[24%] right-[3%] h-[44%] w-[31%] z-[2]" delay={280} />
          <Arch p={beauty} rounded="circle" className="left-[14%] top-[6%] aspect-square w-[19%] z-[2]" delay={360} />
          <Arch p={gadget} rounded="circle" className="right-[8%] top-[2%] aspect-square w-[21%] z-[2]" delay={420} />

          <LeafSpray className="pointer-events-none absolute -right-[9%] bottom-[30%] z-0 h-[50%] w-auto lg:-right-[7%]" />
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ trust / benefits bar */

export function ServiceStrip({ productCount }: { productCount?: number }) {
  const { t, number } = useI18n();
  const items = [
    { icon: Truck, title: t("home.v2.svc.delivery"), body: t("home.v2.svc.deliveryb"), href: "/policies/shipping" },
    { icon: ShieldCheck, title: t("home.v2.svc.payments"), body: t("home.v2.svc.paymentsb"), href: "/policies/privacy" },
    { icon: Package, title: t("home.v2.svc.returns"), body: t("home.v2.svc.returnsb"), href: "/policies/returns" },
    {
      icon: Leaf,
      title: t("home.v2.svc.selection"),
      body: productCount ? t("home.v2.svc.selectionb", { n: number(productCount) }) : t("home.v2.svc.selectionPlain"),
      href: "/categories",
    },
  ];
  return (
    <Reveal as="section" className="container-page relative z-10">
      <ul className="grid grid-cols-2 gap-y-2 rounded-[1.4rem] bg-white px-2 py-4 shadow-card ring-1 ring-black/[0.04] sm:py-5 lg:grid-cols-4 lg:divide-x lg:divide-ink/10">
        {items.map(({ icon: Icon, title, body, href }) => (
          <li key={title} className="flex justify-center sm:justify-start lg:justify-center">
            <Link href={href} className="group flex flex-col items-center gap-2 rounded-xl px-2 py-1.5 text-center sm:flex-row sm:gap-3.5 sm:px-5 sm:text-left">
              <Icon className="h-7 w-7 shrink-0 text-brand-green-logo transition-transform duration-base ease-out group-hover:-translate-y-0.5" strokeWidth={1.8} aria-hidden />
              <span>
                <span className="block text-[13.5px] font-bold text-ink">{title}</span>
                <span className="block text-xs text-ink/55">{body}</span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </Reveal>
  );
}

/* ------------------------------------------------------------------ categories */

const CATEGORY_ORDER = ["electronics", "fashion", "fashion-clothing", "beauty", "beauty-personal-care", "home-kitchen", "furniture-decor", "groceries", "mobiles-accessories", "books-stationery", "sports-fitness"];

export function ShopByCategory({ categories, images }: { categories: Category[]; images: Map<string, ProductSummary> }) {
  const { t } = useI18n();
  const rank = (slug: string) => {
    const i = CATEGORY_ORDER.indexOf(slug);
    return i === -1 ? CATEGORY_ORDER.length : i;
  };
  const list = categories
    .filter((c) => c.product_count > 0)
    .sort((a, b) => rank(a.slug) - rank(b.slug))
    .slice(0, 8);
  return (
    <section id="shop-by-category" className="container-page pt-12" aria-labelledby="shop-by-category-title">
      <SectionHead id="shop-by-category" title={t("home.v2.categories")} href="/categories" linkLabel={t("home.v2.viewAllCategories")} />
      <ul className="no-scrollbar -mx-4 flex snap-x gap-3 overflow-x-auto px-4 pb-3 pt-1 sm:mx-0 sm:grid sm:grid-cols-4 sm:overflow-visible sm:px-0 lg:grid-cols-8">
        {list.map((c, i) => {
          const src = images.get(c.slug)?.primary_image || c.image_url;
          return (
            <Reveal as="li" key={c.id} delay={Math.min(i, 8) * 45} className="w-[7.5rem] shrink-0 snap-start sm:w-auto">
              <Link
                href={`/products?category_slug=${c.slug}`}
                className="group flex h-full flex-col rounded-card bg-white p-2 shadow-card ring-1 ring-black/[0.04] transition-[transform,box-shadow] duration-base ease-out hover:-translate-y-1 hover:shadow-card-hover"
              >
                <span className="relative block aspect-[1.08] overflow-hidden rounded-[0.8rem] bg-cream">
                  <ProductImage src={src} alt="" sizes="(min-width: 1024px) 10vw, (min-width: 640px) 22vw, 7.5rem" className="transition-transform duration-slow ease-out group-hover:scale-[1.08]" />
                </span>
                <span className="flex flex-1 items-center justify-center px-1 pb-1.5 pt-2.5 text-center">
                  <span className="relative text-[13px] font-bold leading-tight text-ink">
                    {c.name}
                    <span aria-hidden className="absolute -bottom-1 left-1/2 h-[2px] w-0 -translate-x-1/2 rounded-full bg-brand-yellow transition-[width] duration-base ease-out group-hover:w-full" />
                  </span>
                </span>
              </Link>
            </Reveal>
          );
        })}
      </ul>
    </section>
  );
}

/* ------------------------------------------------------------------ deals banner */

/**
 * Wide deals advertisement. The percentage comes only from real data: live flash
 * deals (their real maximum discount) or, if none are running, the largest real
 * saving below MRP in the catalogue. Never a made-up number.
 */
export function DealsBanner({ deals, products }: { deals: SaleStreamItem[]; products: ProductSummary[] }) {
  const { t, number } = useI18n();
  const live = deals.filter((d) => d.event_type === "FLASH_DEAL" && d.seconds_remaining > 0);
  const best = [...products].sort((x, y) => discountOf(y) - discountOf(x))[0];
  let pct = 0;
  let line = "";
  let href = "/sale-stream";
  let lead: { src?: string | null; alt: string } | null = null;
  if (live.length) {
    const top = [...live].sort((x, y) => y.discount_pct - x.discount_pct)[0];
    pct = Math.round(top.discount_pct);
    line = t("home.v2.promoFlash", { n: number(live.length) });
    lead = { src: top.image_url, alt: top.product_name };
  } else if (best && discountOf(best) > 0) {
    pct = discountOf(best);
    line = t("home.v2.promoMrp");
    href = "/products";
    lead = { src: best.primary_image, alt: best.name };
  }
  if (!pct || !lead) return null;
  const [extra] = pickProducts(products.filter((p) => p.primary_image !== lead!.src), [/shoe|sneaker|headphone|watch/i]);
  const title = highlightSlot(t("home.v2.promoTitle", { pct: "\u0000" }), (sfx) => <span className="text-brand-yellow">{pct}{sfx}</span>);
  return (
    <Reveal as="section" className="container-page pt-12">
      <CampaignBanner
        tone="green"
        size="wide"
        eyebrow={t("home.v2.promoEyebrow")}
        title={title}
        body={line}
        cta={t("home.v2.promoCta")}
        href={href}
        images={[lead, extra ? { src: extra.primary_image, alt: extra.name } : { alt: "" }]}
        badge="%"
        ariaLabel={`${t("home.v2.promoEyebrow")}: ${t("home.v2.promoTitle", { pct })}`}
      />
    </Reveal>
  );
}

/** Two half-width campaign ads for marketplace features (group buying, auctions). */
export function CampaignRow({ images }: { images: Map<string, ProductSummary> }) {
  const { t } = useI18n();
  const img = (...slugs: string[]) => {
    for (const s of slugs) {
      const p = images.get(s);
      if (p) return [{ src: p.primary_image, alt: p.name }];
    }
    return [];
  };
  return (
    <section className="container-page grid gap-4 pt-12 md:grid-cols-2" aria-label={t("home.v2.promoEyebrow")}>
      <Reveal>
        <CampaignBanner
          tone="yellow"
          size="compact"
          eyebrow={t("home.v2.promo.group.eyebrow")}
          title={t("home.v2.promo.group.title")}
          body={t("home.v2.promo.group.body")}
          cta={t("home.v2.promo.group.cta")}
          href="/community-buying"
          images={img("fashion", "beauty", "home-kitchen", "groceries")}
        />
      </Reveal>
      <Reveal delay={90}>
        <CampaignBanner
          tone="ink"
          size="compact"
          eyebrow={t("home.v2.promo.auction.eyebrow")}
          title={t("home.v2.promo.auction.title")}
          body={t("home.v2.promo.auction.body")}
          cta={t("home.v2.promo.auction.cta")}
          href="/auctions"
          images={img("electronics", "mobiles-accessories", "computers-laptops")}
        />
      </Reveal>
    </section>
  );
}

/* ------------------------------------------------------------------ the basket edit */

const EDITS: { key: string; slugs: string[]; bg: string }[] = [
  { key: "tech", slugs: ["electronics", "computers-laptops", "mobiles-accessories"], bg: "#EDEBE6" },
  { key: "style", slugs: ["fashion", "fashion-clothing"], bg: "#F5ECE2" },
  { key: "home", slugs: ["home-kitchen", "furniture-decor", "home-furniture", "home-appliances"], bg: "#E3EDE5" },
  { key: "beauty", slugs: ["beauty", "beauty-personal-care"], bg: "#F6E8E5" },
  { key: "pantry", slugs: ["groceries"], bg: "#EEF0E0" },
  { key: "active", slugs: ["sports-fitness"], bg: "#E5EBF1" },
  { key: "reading", slugs: ["books-stationery"], bg: "#F1EBDF" },
];

function useRail() {
  const ref = useRef<HTMLUListElement>(null);
  const [edges, setEdges] = useState({ start: true, end: true });
  const update = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    const max = el.scrollWidth - el.clientWidth;
    const x = Math.abs(el.scrollLeft); // RTL scrolls negative
    setEdges({ start: x <= 2, end: x >= max - 2 });
  }, []);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    update();
    el.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    return () => {
      el.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
    };
  }, [update]);
  const go = (dir: 1 | -1) => {
    const el = ref.current;
    if (!el) return;
    const card = el.querySelector("li");
    const step = card ? card.getBoundingClientRect().width + 16 : el.clientWidth * 0.8;
    const rtl = getComputedStyle(el).direction === "rtl" ? -1 : 1;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollBy({ left: dir * step * rtl, behavior: reduce ? "auto" : "smooth" });
  };
  return { ref, edges, go, update };
}

export function BasketEdit({ categories, images }: { categories: Category[]; images: Map<string, ProductSummary> }) {
  const { t } = useI18n();
  const live = new Map(categories.filter((c) => c.product_count > 0).map((c) => [c.slug, c]));
  const cards = EDITS.flatMap((e) => {
    const slug = e.slugs.find((s) => live.has(s));
    if (!slug) return [];
    return [{ ...e, slug, src: live.get(slug)?.image_url || images.get(slug)?.primary_image }];
  });
  const ready = cards.length > 0;
  const rail = useRail();
  const { update } = rail;
  useEffect(() => {
    if (ready) update();
  }, [ready, update]);
  // The section renders after data arrives, so honour a #the-basket-edit link once it exists.
  useEffect(() => {
    if (!ready || window.location.hash !== "#the-basket-edit") return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    requestAnimationFrame(() => document.getElementById("the-basket-edit")?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" }));
  }, [ready]);
  if (!ready) return null;
  const arrow = "press flex h-10 w-10 items-center justify-center rounded-full bg-white text-ink shadow-card ring-1 ring-black/[0.06] hover:bg-ink hover:text-white disabled:pointer-events-none disabled:opacity-40";
  return (
    <section id="the-basket-edit" className="container-page scroll-mt-28 pt-12" aria-labelledby="the-basket-edit-title" aria-roledescription="carousel">
      <SectionHead
        id="the-basket-edit"
        title={t("home.v2.edit")}
        subtitle={t("home.v2.editSub")}
        actions={
          cards.length > 3 ? (
            <div className="hidden gap-2 sm:flex">
              <button type="button" className={arrow} onClick={() => rail.go(-1)} disabled={rail.edges.start} aria-label={t("home.v2.prev")}>
                <ArrowLeft className="h-4 w-4 rtl:rotate-180" />
              </button>
              <button type="button" className={arrow} onClick={() => rail.go(1)} disabled={rail.edges.end} aria-label={t("home.v2.next")}>
                <ArrowRight className="h-4 w-4 rtl:rotate-180" />
              </button>
            </div>
          ) : undefined
        }
      />
      <ul ref={rail.ref} className="no-scrollbar -mx-4 flex snap-x snap-mandatory gap-4 overflow-x-auto scroll-smooth px-4 pb-3 pt-1 sm:mx-0 sm:px-0">
        {cards.map((c, i) => (
          <li key={c.key} className="w-[85%] shrink-0 snap-start sm:w-[calc((100%-1rem)/2)] lg:w-[calc((100%-2rem)/3)]">
            <Reveal delay={Math.min(i, 3) * 90} className="h-full">
              <Link
                href={`/products?category_slug=${c.slug}`}
                style={{ backgroundColor: c.bg }}
                className="group relative flex h-40 overflow-hidden rounded-card shadow-card ring-1 ring-black/[0.04] transition-[transform,box-shadow] duration-base ease-out hover:-translate-y-1 hover:shadow-card-hover sm:h-[10.5rem]"
              >
                <span className="relative z-10 flex w-[52%] flex-col justify-center p-5 sm:p-6">
                  <span className="text-[1.6rem] font-extrabold leading-[1.02] tracking-[-0.02em] text-ink">{t(`home.v2.edit.${c.key}`)}</span>
                  <span className="mt-2 text-xs leading-snug text-ink/65">{t(`home.v2.edit.${c.key}.body`)}</span>
                  <span className="mt-3 inline-flex items-center gap-1.5 text-[13px] font-bold text-ink opacity-0 transition-opacity duration-base group-hover:opacity-100 group-focus-visible:opacity-100">
                    {t("home.v2.explore")}
                    <ArrowRight className="h-3.5 w-3.5 rtl:rotate-180" />
                  </span>
                </span>
                <span className="absolute inset-y-0 right-0 w-[58%] overflow-hidden [mask-image:linear-gradient(to_right,transparent,#000_38%)]">
                  <ProductImage src={c.src} alt="" sizes="(min-width: 1024px) 18vw, (min-width: 640px) 28vw, 50vw" className="transition-transform duration-slow ease-out group-hover:scale-[1.06]" />
                </span>
              </Link>
            </Reveal>
          </li>
        ))}
      </ul>
    </section>
  );
}

/* ------------------------------------------------------------------ product row */

export function ProductRow({ id, title, subtitle, products, href, linkLabel }: { id: string; title: string; subtitle?: string; products: ProductSummary[]; href: string; linkLabel: string }) {
  if (!products.length) return null;
  return (
    <section id={id} className="container-page pt-12" aria-labelledby={`${id}-title`}>
      <SectionHead id={id} title={title} subtitle={subtitle} href={href} linkLabel={linkLabel} accent />
      <ul className="no-scrollbar -mx-4 flex snap-x gap-4 overflow-x-auto px-4 pb-3 pt-1 sm:mx-0 sm:grid sm:grid-cols-3 sm:overflow-visible sm:px-0 lg:grid-cols-5">
        {products.map((p, i) => (
          <Reveal as="li" key={p.id} delay={Math.min(i, 5) * 60} className="w-[46vw] max-w-[15rem] shrink-0 snap-start sm:w-auto sm:max-w-none">
            <ProductCard product={p} />
          </Reveal>
        ))}
      </ul>
    </section>
  );
}
