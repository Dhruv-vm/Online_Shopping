"use client";

import { useEffect } from "react";
import Link from "next/link";
import { ArrowRight, BadgeCheck, PackageCheck, RotateCcw, ShieldCheck, Store, Truck } from "lucide-react";
import { ProductCard } from "@/components/catalogue/product-card";
import { ProductImage } from "@/components/catalogue/product-image";
import { Reveal } from "@/components/motion/reveal";
import { useI18n } from "@/lib/i18n/i18n-context";
import type { SaleStreamItem } from "@/lib/api/phase3";
import type { Category, ProductSummary } from "@/types";

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

function SectionHead({ id, title, subtitle, href, linkLabel, accent = false }: { id: string; title: string; subtitle?: string; href?: string; linkLabel?: string; accent?: boolean }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3 sm:mb-6">
      <div>
        <h2 id={`${id}-title`} className="flex items-center gap-3 text-2xl font-extrabold tracking-tight text-ink sm:text-[1.75rem]">
          {title}
          {accent && <span aria-hidden className="mt-1 hidden h-1 w-12 rounded-full bg-brand-yellow sm:block" />}
        </h2>
        {subtitle && <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>}
      </div>
      {href && linkLabel && (
        <Link href={href} className="group inline-flex items-center gap-1.5 text-sm font-bold text-ink">
          {linkLabel}
          <ArrowRight className="h-4 w-4 transition-transform duration-base ease-out group-hover:translate-x-1" />
        </Link>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ hero */

export function StorefrontHero({ showcase, stats }: { showcase: ProductSummary[]; stats: { products: number; stores: number } | null }) {
  const { t, number } = useI18n();
  const [a, b, c, d] = showcase;
  const tile = (p: ProductSummary | undefined, cls: string, delay: number, eager = false) =>
    p ? (
      <Reveal delay={delay} className={`absolute ${cls}`}>
        <Link href={`/products/${p.slug}`} className="group block h-full w-full overflow-hidden rounded-[1.4rem] bg-white shadow-card-hover ring-1 ring-black/5" aria-label={p.name}>
          <ProductImage src={p.primary_image} alt={p.name} eager={eager} sizes="(min-width: 1024px) 22vw, 40vw" className="transition-transform duration-slow ease-out group-hover:scale-[1.05]" />
        </Link>
      </Reveal>
    ) : null;

  return (
    <section className="relative overflow-hidden" aria-labelledby="hero-title">
      <div className="container-page grid items-center gap-10 pb-10 pt-8 lg:grid-cols-[1.05fr_1fr] lg:pb-14 lg:pt-12">
        <div className="relative z-10">
          <Reveal>
            <p className="flex items-center gap-3 text-xs font-bold uppercase tracking-[0.18em] text-ink/70">
              {t("home.v2.eyebrow")}
              <span aria-hidden className="h-[3px] w-10 rounded-full bg-brand-yellow" />
            </p>
          </Reveal>
          <Reveal delay={80}>
            <h1 id="hero-title" className="mt-4 text-[2.6rem] font-extrabold leading-[1.02] tracking-[-0.03em] text-ink sm:text-6xl xl:text-[4.25rem]">
              {t("home.v2.title1")}
              <br />
              <span className="relative inline-block px-3 sm:-ml-3">
                <span aria-hidden className="absolute inset-x-0 bottom-[0.06em] top-[0.12em] -z-10 rounded-full bg-brand-yellow" />
                {t("home.v2.title2")}
              </span>{" "}
              {t("home.v2.title3")}
            </h1>
          </Reveal>
          <Reveal delay={160}>
            <p className="mt-5 max-w-md text-base leading-relaxed text-ink/70 sm:text-lg">{t("home.v2.subtitle")}</p>
          </Reveal>
          <Reveal delay={240} className="mt-7 flex flex-wrap items-center gap-3">
            <Link href="/products" className="press group inline-flex h-12 items-center gap-2 rounded-full bg-brand-yellow pl-6 pr-5 text-[15px] font-bold text-ink shadow-sm hover:bg-brand-yellow-dark">
              {t("home.v2.cta")}
              <ArrowRight className="h-4 w-4 transition-transform duration-base ease-out group-hover:translate-x-1" />
            </Link>
            <Link href="/sale-stream" className="press inline-flex h-12 items-center rounded-full px-5 text-[15px] font-bold text-ink ring-1 ring-ink/15 hover:ring-ink/40">
              {t("nav.deals")}
            </Link>
          </Reveal>
          <Reveal delay={320}>
            <ul className="mt-8 flex flex-wrap items-center gap-x-5 gap-y-3 text-sm font-semibold text-ink/80">
              <li className="flex items-center gap-2">
                <Store className="h-4 w-4" aria-hidden />
                {stats ? t("home.v2.trustStores", { n: number(stats.stores) }) : t("home.v2.trustStoresPlain")}
              </li>
              <li aria-hidden className="hidden h-4 w-px bg-ink/15 sm:block" />
              <li className="flex items-center gap-2">
                <ShieldCheck className="h-4 w-4" aria-hidden /> {t("home.v2.trustPayments")}
              </li>
              <li aria-hidden className="hidden h-4 w-px bg-ink/15 sm:block" />
              <li className="flex items-center gap-2">
                <Truck className="h-4 w-4" aria-hidden /> {t("home.v2.trustTracking")}
              </li>
            </ul>
          </Reveal>
        </div>

        {/* Product showcase on the yellow disc (reference composition), real products only */}
        <div className="relative mx-auto aspect-[1.12] w-full max-w-[22rem] sm:max-w-[32rem] lg:max-w-[36rem]">
          <Reveal className="absolute inset-[6%_2%_4%_10%]" delay={60}>
            <div className="h-full w-full rounded-full bg-brand-yellow" />
          </Reveal>
          <span aria-hidden className="absolute left-[2%] top-[10%] h-24 w-24 rounded-full border-[10px] border-ink/[0.06]" />
          {tile(a, "left-[6%] top-[16%] h-[46%] w-[40%] -rotate-3", 120, true)}
          {tile(b, "right-[4%] top-[4%] h-[42%] w-[36%] rotate-3", 200, true)}
          {tile(c, "bottom-[6%] left-[24%] h-[42%] w-[36%] rotate-2", 280)}
          {tile(d, "bottom-[12%] right-[2%] h-[34%] w-[28%] -rotate-2", 360)}
          {stats && (
            <Reveal delay={420} className="absolute bottom-[2%] left-[2%]">
              <div className="rounded-2xl bg-ink px-4 py-3 text-white shadow-nav">
                <p className="text-2xl font-extrabold leading-none text-brand-yellow">{number(stats.products)}</p>
                <p className="mt-1 text-[11px] font-semibold text-white/70">{t("home.v2.productsLive")}</p>
              </div>
            </Reveal>
          )}
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ service strip */

export function ServiceStrip() {
  const { t } = useI18n();
  const items = [
    { icon: BadgeCheck, title: t("home.v2.svc1"), body: t("home.v2.svc1b"), href: "/retailers" },
    { icon: ShieldCheck, title: t("home.v2.svc2"), body: t("home.v2.svc2b"), href: "/policies/privacy" },
    { icon: RotateCcw, title: t("home.v2.svc3"), body: t("home.v2.svc3b"), href: "/policies/returns" },
    { icon: PackageCheck, title: t("home.v2.svc4"), body: t("home.v2.svc4b"), href: "/policies/shipping" },
  ];
  return (
    <Reveal as="section" className="container-page">
      <ul className="grid grid-cols-2 gap-y-4 rounded-card bg-white px-4 py-5 shadow-card ring-1 ring-black/[0.04] lg:grid-cols-4 lg:divide-x lg:divide-ink/10 lg:px-2">
        {items.map(({ icon: Icon, title, body, href }) => (
          <li key={title}>
            <Link href={href} className="group flex items-center gap-3 rounded-xl px-3 py-1 sm:px-5">
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-cream transition-colors duration-base group-hover:bg-brand-yellow">
                <Icon className="h-5 w-5 text-ink" aria-hidden />
              </span>
              <span>
                <span className="block text-sm font-bold text-ink">{title}</span>
                <span className="hidden text-xs text-muted-foreground sm:block">{body}</span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </Reveal>
  );
}

/* ------------------------------------------------------------------ categories */

export function ShopByCategory({ categories, images }: { categories: Category[]; images: Map<string, ProductSummary> }) {
  const { t } = useI18n();
  const list = categories.filter((c) => c.product_count > 0);
  return (
    <section id="shop-by-category" className="container-page pt-12" aria-labelledby="shop-by-category-title">
      <SectionHead id="shop-by-category" title={t("home.v2.categories")} href="/categories" linkLabel={t("home.v2.viewAllCategories")} />
      <ul className="no-scrollbar -mx-4 flex snap-x gap-3 overflow-x-auto px-4 pb-2 sm:mx-0 sm:grid sm:grid-cols-5 sm:overflow-visible sm:px-0 lg:grid-cols-10 lg:gap-2.5">
        {list.map((c, i) => {
          const p = images.get(c.slug);
          return (
            <Reveal as="li" key={c.id} delay={Math.min(i, 9) * 45} className="w-28 shrink-0 snap-start sm:w-auto">
              <Link
                href={`/products?category_slug=${c.slug}`}
                className="group relative flex h-full flex-col overflow-hidden rounded-card bg-white p-2 shadow-card ring-1 ring-black/[0.04] transition-[transform,box-shadow,background-color] duration-base ease-out hover:-translate-y-1 hover:bg-ink hover:shadow-card-hover"
              >
                <span className="relative block aspect-square overflow-hidden rounded-[0.85rem] bg-cream">
                  <ProductImage src={p?.primary_image} alt="" sizes="(min-width: 1024px) 9vw, (min-width: 640px) 18vw, 7rem" className="transition-transform duration-slow ease-out group-hover:scale-[1.08]" />
                </span>
                <span className="flex flex-1 items-center px-1 pb-1 pt-2.5">
                  <span className="text-[12.5px] font-bold leading-tight text-ink transition-colors duration-base group-hover:text-white">{c.name}</span>
                </span>
                <span aria-hidden className="absolute right-3 top-3 flex h-7 w-7 translate-y-1 items-center justify-center rounded-full bg-brand-yellow opacity-0 shadow-sm transition-all duration-base ease-out group-hover:translate-y-0 group-hover:opacity-100">
                  <ArrowRight className="h-3.5 w-3.5 text-ink" />
                </span>
              </Link>
            </Reveal>
          );
        })}
      </ul>
    </section>
  );
}

/* ------------------------------------------------------------------ promo banner */

/**
 * Wide campaign banner (reference composition). Content comes only from real data:
 * live flash deals (their real maximum discount) or, if none are running, the
 * largest real saving below MRP in the catalogue. Never a made-up percentage.
 */
export function PromoBanner({ deals, products }: { deals: SaleStreamItem[]; products: ProductSummary[] }) {
  const { t, number } = useI18n();
  const live = deals.filter((d) => d.event_type === "FLASH_DEAL" && d.seconds_remaining > 0);
  const best = [...products].sort((x, y) => discountOf(y) - discountOf(x))[0];
  let pct = 0;
  let line = "";
  let href = "/sale-stream";
  let img: string | null | undefined = null;
  let imgAlt = "";
  if (live.length) {
    const top = [...live].sort((x, y) => y.discount_pct - x.discount_pct)[0];
    pct = Math.round(top.discount_pct);
    line = t("home.v2.promoFlash", { n: number(live.length) });
    img = top.image_url;
    imgAlt = top.product_name;
  } else if (best && discountOf(best) > 0) {
    pct = discountOf(best);
    line = t("home.v2.promoMrp");
    href = "/products";
    img = best.primary_image;
    imgAlt = best.name;
  }
  if (!pct) return null;
  const extras = products.filter((p) => p.primary_image && p.primary_image !== img).slice(0, 1);
  return (
    <Reveal as="section" className="container-page pt-12">
      <Link href={href} aria-label={`${t("home.v2.promoEyebrow")}: ${t("home.v2.promoTitle", { pct })}`} className="group relative block overflow-hidden rounded-hero bg-ink text-white shadow-card-hover">
        {/* Yellow field with a curved edge and a deep-green accent, as in the reference */}
        <svg aria-hidden className="absolute inset-0 hidden h-full w-full sm:block" viewBox="0 0 1000 300" preserveAspectRatio="none">
          <path d="M560 0 C 470 80, 640 170, 500 300 L1000 300 L1000 0 Z" fill="#FDCD1E" />
          <path d="M430 300 C 500 240, 470 170, 575 105 C 520 190, 600 250, 548 300 Z" fill="#0F2A1C" />
        </svg>
        <div className="relative grid min-h-[13rem] items-center gap-4 p-7 sm:min-h-[15rem] sm:grid-cols-[1.05fr_1fr] sm:p-10">
          <div className="max-w-md">
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-brand-yellow">{t("home.v2.promoEyebrow")}</p>
            <p className="mt-2 text-4xl font-extrabold leading-[1.02] tracking-tight sm:text-[3.4rem]">{t("home.v2.promoTitle", { pct })}</p>
            <p className="mt-3 text-sm text-white/75 sm:text-base">{line}</p>
            <span className="press mt-6 inline-flex h-11 items-center gap-2 rounded-full bg-brand-yellow pl-5 pr-4 text-sm font-bold text-ink transition-colors group-hover:bg-white">
              {t("home.v2.promoCta")}
              <ArrowRight className="h-4 w-4 transition-transform duration-base ease-out group-hover:translate-x-1" />
            </span>
          </div>
          <div className="relative hidden h-full min-h-[11rem] sm:block">
            {img && (
              <span className="absolute right-[18%] top-1/2 block h-[88%] w-[46%] -translate-y-1/2 rotate-3 overflow-hidden rounded-[1.4rem] bg-white shadow-card-hover ring-4 ring-white/70 transition-transform duration-slow ease-out group-hover:rotate-1 group-hover:scale-[1.03]">
                <ProductImage src={img} alt={imgAlt} sizes="24vw" />
              </span>
            )}
            {extras[0] && (
              <span className="absolute right-0 top-[58%] block h-[62%] w-[30%] -translate-y-1/2 -rotate-6 overflow-hidden rounded-[1.2rem] bg-white shadow-card-hover ring-4 ring-white/70 transition-transform duration-slow ease-out group-hover:-rotate-3">
                <ProductImage src={extras[0].primary_image} alt={extras[0].name} sizes="16vw" />
              </span>
            )}
          </div>
        </div>
      </Link>
    </Reveal>
  );
}

/* ------------------------------------------------------------------ the basket edit */

const EDITS = [
  { slug: "electronics", key: "tech", tone: "dark" },
  { slug: "fashion-clothing", key: "style", tone: "light" },
  { slug: "furniture-decor", alt: "home-kitchen", key: "home", tone: "cream" },
] as const;

export function BasketEdit({ categories, images }: { categories: Category[]; images: Map<string, ProductSummary> }) {
  const { t } = useI18n();
  const cards = EDITS.map((e) => {
    const slug = [e.slug, "alt" in e ? e.alt : null].find((s) => s && categories.some((c) => c.slug === s && c.product_count > 0));
    return slug ? { ...e, slug, product: images.get(slug) } : null;
  }).filter(Boolean) as { slug: string; key: string; tone: string; product?: ProductSummary }[];
  const ready = cards.length > 0;
  // The section renders after data arrives, so honour a #the-basket-edit link once it exists.
  useEffect(() => {
    if (!ready || window.location.hash !== "#the-basket-edit") return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    requestAnimationFrame(() => document.getElementById("the-basket-edit")?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" }));
  }, [ready]);
  if (!ready) return null;
  return (
    <section id="the-basket-edit" className="container-page scroll-mt-28 pt-12" aria-labelledby="the-basket-edit-title">
      <SectionHead id="the-basket-edit" title={t("home.v2.edit")} subtitle={t("home.v2.editSub")} />
      <div className="grid gap-4 lg:grid-cols-3">
        {cards.map((c, i) => (
          <Reveal key={c.key} delay={i * 90}>
            <Link
              href={`/products?category_slug=${c.slug}`}
              className={`group relative flex h-48 overflow-hidden rounded-card shadow-card ring-1 ring-black/[0.04] transition-[transform,box-shadow] duration-base ease-out hover:-translate-y-1 hover:shadow-card-hover sm:h-52 ${
                c.tone === "dark" ? "bg-ink text-white" : c.tone === "light" ? "bg-white text-ink" : "bg-cream text-ink"
              }`}
            >
              <span className="relative z-10 flex w-[55%] flex-col justify-center p-6">
                <span className="text-2xl font-extrabold leading-[1.05] tracking-tight">{t(`home.v2.edit.${c.key}`)}</span>
                <span className={`mt-2 text-xs ${c.tone === "dark" ? "text-white/70" : "text-ink/60"}`}>{t(`home.v2.edit.${c.key}.body`)}</span>
                <span className={`mt-4 inline-flex items-center gap-1.5 text-sm font-bold ${c.tone === "dark" ? "text-brand-yellow" : "text-ink"}`}>
                  {t("home.v2.explore")}
                  <ArrowRight className="h-4 w-4 transition-transform duration-base ease-out group-hover:translate-x-1" />
                </span>
              </span>
              <span className="absolute inset-y-0 right-0 w-[56%] overflow-hidden [mask-image:linear-gradient(to_right,transparent,#000_40%)]">
                {c.product && <ProductImage src={c.product.primary_image} alt="" sizes="(min-width: 768px) 18vw, 55vw" className="transition-transform duration-slow ease-out group-hover:scale-[1.06]" />}
              </span>
            </Link>
          </Reveal>
        ))}
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ product row */

export function ProductRow({ id, title, subtitle, products, href, linkLabel }: { id: string; title: string; subtitle?: string; products: ProductSummary[]; href: string; linkLabel: string }) {
  if (!products.length) return null;
  return (
    <section id={id} className="container-page pt-12" aria-labelledby={`${id}-title`}>
      <SectionHead id={id} title={title} subtitle={subtitle} href={href} linkLabel={linkLabel} accent />
      <ul className="no-scrollbar -mx-4 flex snap-x gap-4 overflow-x-auto px-4 pb-3 sm:mx-0 sm:grid sm:grid-cols-3 sm:overflow-visible sm:px-0 lg:grid-cols-5">
        {products.map((p, i) => (
          <Reveal as="li" key={p.id} delay={Math.min(i, 5) * 60} className="w-[46vw] max-w-[15rem] shrink-0 snap-start sm:w-auto sm:max-w-none">
            <ProductCard product={p} />
          </Reveal>
        ))}
      </ul>
    </section>
  );
}
