"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  BadgeCheck,
  Bot,
  CreditCard,
  Gavel,
  LineChart,
  MapPin,
  RotateCcw,
  Search,
  ShieldCheck,
  Sparkles,
  Store,
  Target,
  TrendingDown,
  Users,
  Zap,
} from "lucide-react";
import { ProductCard } from "@/components/catalogue/product-card";
import { ProductImage } from "@/components/catalogue/product-image";
import { Rail, Section, SkeletonCards } from "@/components/home/section";
import { CampaignCard } from "@/components/phase3/campaign-card";
import { Countdown } from "@/components/phase3/kit";
import { apiClient } from "@/lib/api/client";
import { browseDemandPools, getSaleStream, listCampaigns, type DemandPool, type GroupBuyCampaign, type SaleStreamItem } from "@/lib/api/phase3";
import { useI18n } from "@/lib/i18n/i18n-context";
import { getPincode, PINCODE_EVENT } from "@/lib/location";
import { getRecent, type RecentProduct } from "@/lib/recent";
import type { Category, ProductSummary, Retailer } from "@/types";

function useHomeData() {
  const [categories, setCategories] = useState<Category[] | null>(null);
  const [featured, setFeatured] = useState<ProductSummary[] | null>(null);
  const [recommended, setRecommended] = useState<ProductSummary[] | null>(null);
  const [retailers, setRetailers] = useState<Retailer[] | null>(null);
  const [stream, setStream] = useState<SaleStreamItem[] | null>(null);
  const [groups, setGroups] = useState<GroupBuyCampaign[] | null>(null);
  const [demand, setDemand] = useState<DemandPool[] | null>(null);
  useEffect(() => {
    apiClient.getCategories().then(setCategories).catch(() => setCategories([]));
    apiClient.getProducts({ in_stock: true, sort_by: "newest", limit: 10 }).then((r) => setFeatured(r.items)).catch(() => setFeatured([]));
    apiClient.getProducts({ in_stock: true, sort_by: "price_asc", limit: 10 }).then((r) => setRecommended(r.items)).catch(() => setRecommended([]));
    apiClient.getRetailers().then(setRetailers).catch(() => setRetailers([]));
    getSaleStream({ limit: 12 }).then((r) => setStream(r.items)).catch(() => setStream([]));
    listCampaigns({ limit: 4 }).then((r) => setGroups(r.items)).catch(() => setGroups([]));
    browseDemandPools({ limit: 6 }).then((r) => setDemand(r.items)).catch(() => setDemand([]));
  }, []);
  return { categories, featured, recommended, retailers, stream, groups, demand };
}

function Hero({ stats }: { stats: { products: number; stores: number; departments: number } | null }) {
  const { t, number } = useI18n();
  const router = useRouter();
  const [q, setQ] = useState("");
  const [pin, setPin] = useState<string | null>(null);
  useEffect(() => {
    setPin(getPincode());
    const on = (e: Event) => setPin((e as CustomEvent<string | null>).detail ?? null);
    window.addEventListener(PINCODE_EVENT, on);
    return () => window.removeEventListener(PINCODE_EVENT, on);
  }, []);
  return (
    <section className="bg-brand-dark text-white">
      <div className="container-page grid gap-10 py-12 sm:py-16 lg:grid-cols-[1.25fr_1fr] lg:items-center">
        <div>
          <p className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-semibold text-brand-yellow">
            <Sparkles className="h-3.5 w-3.5" /> {t("home.hero.badge")}
          </p>
          <h1 className="mt-4 text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl">{t("home.hero.title")}</h1>
          <p className="mt-4 max-w-xl text-base text-white/80 sm:text-lg">{t("home.hero.subtitle")}</p>
          <form
            role="search"
            onSubmit={(e) => {
              e.preventDefault();
              if (q.trim()) router.push(`/search?q=${encodeURIComponent(q.trim())}`);
            }}
            className="mt-6 flex max-w-xl overflow-hidden rounded-xl bg-white shadow-lg"
          >
            <label htmlFor="hero-search" className="sr-only">{t("common.search")}</label>
            <Search className="ml-3 mt-3.5 h-5 w-5 shrink-0 text-muted-foreground" />
            <input id="hero-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("common.searchPlaceholder")} className="h-12 flex-1 px-3 text-sm text-charcoal focus:outline-none" />
            <button type="submit" className="m-1.5 rounded-lg bg-brand-yellow px-5 text-sm font-bold text-charcoal">{t("common.search")}</button>
          </form>
          <p className="mt-3 flex items-center gap-1.5 text-xs text-white/70">
            <MapPin className="h-3.5 w-3.5" />
            {pin ? t("home.hero.deliveringTo", { pin }) : t("home.hero.setPin")}
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link href="/products" className="rounded-lg bg-brand px-5 py-3 text-sm font-semibold text-white hover:bg-brand/90">{t("home.hero.ctaShop")}</Link>
            <Link href="/sale-stream" className="rounded-lg border border-white/30 px-5 py-3 text-sm font-semibold hover:bg-white/10">{t("home.hero.ctaDeals")}</Link>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-3 text-center">
          {[
            { v: stats?.products, k: "home.hero.statProducts" },
            { v: stats?.stores, k: "home.hero.statStores" },
            { v: stats?.departments, k: "home.hero.statDepartments" },
          ].map((s) => (
            <div key={s.k} className="rounded-xl bg-white/10 p-4">
              <div className="text-3xl font-extrabold text-brand-yellow">{s.v == null ? "…" : number(s.v)}</div>
              <div className="mt-1 text-xs text-white/75">{t(s.k)}</div>
            </div>
          ))}
          <p className="col-span-3 text-[11px] text-white/55">{t("home.hero.statsNote")}</p>
        </div>
      </div>
    </section>
  );
}

function StreamTile({ e }: { e: SaleStreamItem }) {
  const { t, money } = useI18n();
  return (
    <Link href={`/products/${e.product_id}`} className="group overflow-hidden rounded-xl border bg-white">
      <div className="relative aspect-[4/3] bg-surface">
        <ProductImage src={e.image_url} alt={e.product_name} />
        <span className="absolute left-2 top-2 rounded bg-brand-yellow px-1.5 py-0.5 text-[11px] font-bold text-charcoal">{t(`stream.${e.event_type}`)}</span>
      </div>
      <div className="space-y-1 p-3 text-sm">
        <p className="line-clamp-2 font-semibold group-hover:text-brand-dark">{e.product_name}</p>
        <p className="text-xs text-muted-foreground">{e.retailer_name}</p>
        <p>
          <span className="font-bold">{money(e.deal_price_paise)}</span>{" "}
          {e.old_price_paise > e.deal_price_paise && <span className="text-xs text-muted-foreground line-through">{money(e.old_price_paise)}</span>}
          {e.discount_pct > 0 && <span className="ml-1 text-xs font-semibold text-brand">−{Math.round(e.discount_pct)}%</span>}
        </p>
        <p className="text-[11px] text-muted-foreground">
          {t("common.timeLeft")}: <Countdown seconds={e.seconds_remaining} /> · {t("common.onlyLeft", { n: e.stock_remaining })}
        </p>
      </div>
    </Link>
  );
}

export default function HomePage() {
  const { t, number } = useI18n();
  const d = useHomeData();
  const [recent, setRecent] = useState<RecentProduct[]>([]);
  useEffect(() => setRecent(getRecent()), []);

  const brands = useMemo(() => {
    const counts = new Map<string, number>();
    [...(d.featured ?? []), ...(d.recommended ?? [])].forEach((p) => counts.set(p.brand, (counts.get(p.brand) ?? 0) + 1));
    return [...counts.keys()].sort((a, b) => a.localeCompare(b)).slice(0, 12);
  }, [d.featured, d.recommended]);

  const stats = d.categories && d.retailers ? {
    products: d.categories.reduce((s, c) => s + (c.product_count ?? 0), 0),
    stores: d.retailers.length,
    departments: d.categories.filter((c) => c.product_count > 0).length,
  } : null;
  const offers = (d.stream ?? []).filter((e) => e.event_type === "FLASH_DEAL");
  const drops = (d.stream ?? []).filter((e) => e.event_type === "PRICE_DROP");

  return (
    <div>
      <Hero stats={stats} />

      <Section id="departments" title={t("home.departments.title")} subtitle={t("home.departments.subtitle")} href="/categories" linkLabel={t("common.viewAll")}>
        {!d.categories ? <SkeletonCards /> : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {d.categories.filter((c) => c.product_count > 0).map((c) => (
              <Link key={c.id} href={`/products?category_slug=${c.slug}`} className="group overflow-hidden rounded-xl border bg-white">
                <div className="aspect-[16/10] bg-surface"><ProductImage src={c.image_url} alt={c.name} /></div>
                <div className="p-3">
                  <p className="text-sm font-semibold group-hover:text-brand-dark">{c.name}</p>
                  <p className="text-xs text-muted-foreground">{t("home.departments.count", { n: c.product_count })}</p>
                </div>
              </Link>
            ))}
          </div>
        )}
      </Section>

      <Section id="featured" title={t("home.featured.title")} subtitle={t("home.featured.subtitle")} href="/products" linkLabel={t("common.viewAll")} tone="tint">
        {!d.featured ? <SkeletonCards /> : d.featured.length === 0 ? <p className="text-sm text-muted-foreground">{t("home.empty")}</p> : (
          <Rail>{d.featured.map((p) => <ProductCard key={p.id} product={p} />)}</Rail>
        )}
      </Section>

      <Section id="brands" title={t("home.brands.title")} subtitle={t("home.brands.subtitle")}>
        <div className="flex flex-wrap gap-2">
          {brands.map((b) => (
            <Link key={b} href={`/search?q=${encodeURIComponent(b)}`} className="rounded-full border bg-white px-4 py-2 text-sm font-semibold hover:border-brand hover:text-brand-dark">{b}</Link>
          ))}
        </div>
        <p className="mt-3 text-xs text-muted-foreground">{t("home.brands.note")}</p>
      </Section>

      <Section id="partners" title={t("home.partners.title")} subtitle={t("home.partners.subtitle")} href="/retailers" linkLabel={t("common.viewAll")} tone="tint">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {(d.retailers ?? []).slice(0, 8).map((r) => (
            <Link key={r.id} href={`/retailers/${r.slug}`} className="flex items-start gap-3 rounded-xl border bg-white p-4 hover:border-brand">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-brand-light text-brand-dark">
                {r.logo_url ? <ProductImage src={r.logo_url} alt={r.name} /> : <Store className="h-5 w-5" />}
              </span>
              <span className="min-w-0">
                <span className="flex items-center gap-1 font-semibold"><span className="truncate">{r.name}</span><BadgeCheck className="h-4 w-4 shrink-0 text-brand" aria-label={t("home.partners.verified")} /></span>
                <span className="line-clamp-2 text-xs text-muted-foreground">{r.description}</span>
              </span>
            </Link>
          ))}
        </div>
      </Section>

      <Section id="offers" title={t("home.offers.title")} subtitle={t("home.offers.subtitle")} href="/sale-stream" linkLabel={t("common.viewAll")}>
        {!d.stream ? <SkeletonCards /> : offers.length === 0 ? <p className="text-sm text-muted-foreground">{t("home.offers.empty")}</p> : (
          <Rail>{offers.slice(0, 5).map((e) => <StreamTile key={e.id} e={e} />)}</Rail>
        )}
      </Section>

      <Section id="demand" title={t("home.demand.title")} subtitle={t("home.demand.subtitle")} tone="tint">
        {d.demand && d.demand.length > 0 ? (
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {d.demand.map((p) => (
              <li key={p.id} className="flex items-center justify-between rounded-xl border bg-white p-4 text-sm">
                <span>
                  <span className="block font-semibold">{p.display_name}</span>
                  <span className="text-xs text-muted-foreground">{t("requests.shoppers", { n: p.unique_users_count })}{p.pincode ? ` · PIN ${p.pincode}` : ""}</span>
                </span>
                <Link href={`/search?q=${encodeURIComponent(p.display_name)}`} className="text-xs font-semibold text-brand-dark underline">{t("home.demand.cta")}</Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">{t("home.demand.empty")}</p>
        )}
      </Section>

      <Section id="community" title={t("home.community.title")} subtitle={t("home.community.subtitle")} href="/community-buying" linkLabel={t("common.viewAll")}>
        {!d.groups ? <SkeletonCards n={4} /> : d.groups.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("group.noOpen")} <Link href="/community-buying" className="text-brand underline">{t("group.startOwn")}</Link></p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {d.groups.map((c) => <CampaignCard key={c.id} c={c} onChange={() => undefined} />)}
          </div>
        )}
      </Section>

      <Section id="features" title={t("home.features.title")} subtitle={t("home.features.subtitle")} tone="dark">
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[
            { icon: Gavel, k: "home.dukaan", href: "/auctions" },
            { icon: LineChart, k: "home.price", href: "/products" },
            { icon: Bot, k: "home.assistant", href: "/assistant" },
            { icon: Users, k: "home.rfq", href: "/exchange" },
          ].map(({ icon: Icon, k, href }) => (
            <Link key={k} href={href} className="rounded-xl bg-white/10 p-5 hover:bg-white/15">
              <Icon className="h-7 w-7 text-brand-yellow" />
              <h3 className="mt-3 font-semibold">{t(`${k}.title`)}</h3>
              <p className="mt-1 text-sm text-white/75">{t(`${k}.body`)}</p>
              <span className="mt-3 inline-block text-sm font-semibold text-brand-yellow">{t(`${k}.cta`)} →</span>
            </Link>
          ))}
        </div>
      </Section>

      <Section id="stream" title={t("home.stream.title")} subtitle={t("home.stream.subtitle")} href="/sale-stream" linkLabel={t("common.viewAll")}>
        {!d.stream ? <SkeletonCards /> : d.stream.length === 0 ? <p className="text-sm text-muted-foreground">{t("home.stream.empty")}</p> : (
          <Rail>{(drops.length ? drops : d.stream).slice(0, 5).map((e) => <StreamTile key={e.id} e={e} />)}</Rail>
        )}
      </Section>

      <Section id="missions" title={t("home.missions.title")} subtitle={t("home.missions.subtitle")} tone="tint">
        <div className="grid gap-3 sm:grid-cols-3">
          {["home.missions.kitchen", "home.missions.desk", "home.missions.grocery"].map((k) => (
            <Link key={k} href="/missions" className="flex items-center gap-3 rounded-xl border bg-white p-4 hover:border-brand">
              <Target className="h-6 w-6 text-brand" />
              <span className="text-sm font-semibold">{t(k)}</span>
            </Link>
          ))}
        </div>
      </Section>

      {recent.length > 0 && (
        <Section id="recent" title={t("home.recent.title")}>
          <Rail>
            {recent.map((p) => (
              <Link key={p.slug} href={`/products/${p.slug}`} className="overflow-hidden rounded-xl border bg-white">
                <div className="aspect-square bg-surface"><ProductImage src={p.image} alt={p.name} /></div>
                <div className="p-3 text-sm">
                  <p className="text-[11px] uppercase text-muted-foreground">{p.brand}</p>
                  <p className="line-clamp-2 font-semibold">{p.name}</p>
                </div>
              </Link>
            ))}
          </Rail>
        </Section>
      )}

      <Section id="recommended" title={t("home.recommended.title")} subtitle={t("home.recommended.subtitle")} href="/products" linkLabel={t("common.viewAll")}>
        {!d.recommended ? <SkeletonCards /> : <Rail>{d.recommended.map((p) => <ProductCard key={p.id} product={p} />)}</Rail>}
      </Section>

      <Section id="trust" title={t("home.trust.title")} tone="tint">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { icon: ShieldCheck, k: "home.trust.verified" },
            { icon: CreditCard, k: "home.trust.payments" },
            { icon: TrendingDown, k: "home.trust.prices" },
            { icon: RotateCcw, k: "home.trust.returns" },
          ].map(({ icon: Icon, k }) => (
            <div key={k} className="rounded-xl border bg-white p-5">
              <Icon className="h-7 w-7 text-brand" />
              <h3 className="mt-3 font-semibold">{t(`${k}.title`)}</h3>
              <p className="mt-1 text-sm text-muted-foreground">{t(`${k}.body`)}</p>
            </div>
          ))}
        </div>
        <p className="mt-4 flex items-center gap-1.5 text-xs text-muted-foreground"><Zap className="h-3.5 w-3.5" /> {t("home.trust.counts", { stores: number(stats?.stores ?? 0) })}</p>
      </Section>
    </div>
  );
}
