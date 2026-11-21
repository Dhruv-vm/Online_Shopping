"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  BadgeCheck,
  Bot,
  CreditCard,
  Gavel,
  LineChart,
  RotateCcw,
  ShieldCheck,
  Store,
  Target,
  TrendingDown,
  Users,
  Zap,
} from "lucide-react";
import { ProductCard } from "@/components/catalogue/product-card";
import { ProductImage } from "@/components/catalogue/product-image";
import { Rail, Section, SkeletonCards } from "@/components/home/section";
import { BasketEdit, imageByCategory, ProductRow, PromoBanner, ServiceStrip, ShopByCategory, StorefrontHero } from "@/components/home/storefront";
import { CampaignCard } from "@/components/phase3/campaign-card";
import { Countdown } from "@/components/phase3/kit";
import { apiClient } from "@/lib/api/client";
import { browseDemandPools, getSaleStream, listCampaigns, type DemandPool, type GroupBuyCampaign, type SaleStreamItem } from "@/lib/api/phase3";
import { useI18n } from "@/lib/i18n/i18n-context";
import { getRecent, type RecentProduct } from "@/lib/recent";
import type { Category, ProductSummary, Retailer } from "@/types";

function useHomeData() {
  const [categories, setCategories] = useState<Category[] | null>(null);
  const [featured, setFeatured] = useState<ProductSummary[] | null>(null);
  const [catalogue, setCatalogue] = useState<ProductSummary[] | null>(null);
  const [recommended, setRecommended] = useState<ProductSummary[] | null>(null);
  const [retailers, setRetailers] = useState<Retailer[] | null>(null);
  const [stream, setStream] = useState<SaleStreamItem[] | null>(null);
  const [groups, setGroups] = useState<GroupBuyCampaign[] | null>(null);
  const [demand, setDemand] = useState<DemandPool[] | null>(null);
  useEffect(() => {
    apiClient.getCategories().then(setCategories).catch(() => setCategories([]));
    apiClient.getProducts({ in_stock: true, sort_by: "newest", limit: 10 }).then((r) => setFeatured(r.items)).catch(() => setFeatured([]));
    apiClient.getProducts({ in_stock: true, sort_by: "newest", limit: 48 }).then((r) => setCatalogue(r.items)).catch(() => setCatalogue([]));
    apiClient.getProducts({ in_stock: true, sort_by: "price_asc", limit: 10 }).then((r) => setRecommended(r.items)).catch(() => setRecommended([]));
    apiClient.getRetailers().then(setRetailers).catch(() => setRetailers([]));
    getSaleStream({ limit: 12 }).then((r) => setStream(r.items)).catch(() => setStream([]));
    listCampaigns({ limit: 4 }).then((r) => setGroups(r.items)).catch(() => setGroups([]));
    browseDemandPools({ limit: 6 }).then((r) => setDemand(r.items)).catch(() => setDemand([]));
  }, []);
  return { categories, featured, catalogue, recommended, retailers, stream, groups, demand };
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
  const catImages = useMemo(() => imageByCategory(d.catalogue ?? []), [d.catalogue]);
  const showcase = useMemo(() => {
    const prefer = ["electronics", "fashion-clothing", "beauty-personal-care", "furniture-decor", "home-kitchen", "sports-fitness"];
    const picks: ProductSummary[] = [];
    for (const slug of prefer) {
      const p = catImages.get(slug);
      if (p && picks.length < 4) picks.push(p);
    }
    return picks;
  }, [catImages]);
  // "Trending" only when the Sale Stream reports real hot sellers.
  const trending = useMemo(() => {
    const ids = new Set((d.stream ?? []).filter((e) => e.event_type === "HOT_SELLER").map((e) => e.product_id));
    return (d.catalogue ?? []).filter((p) => ids.has(p.id)).slice(0, 10);
  }, [d.stream, d.catalogue]);
  const drops = (d.stream ?? []).filter((e) => e.event_type === "PRICE_DROP");

  return (
    <div>
      <StorefrontHero showcase={showcase} stats={stats} />
      <ServiceStrip />
      {d.categories && d.catalogue ? (
        <ShopByCategory categories={d.categories} images={catImages} />
      ) : (
        <div className="container-page pt-12"><SkeletonCards /></div>
      )}
      {d.catalogue && <PromoBanner deals={d.stream ?? []} products={d.catalogue} />}
      {d.categories && d.catalogue && <BasketEdit categories={d.categories} images={catImages} />}
      {trending.length > 0 ? (
        <ProductRow id="trending" title={t("home.v2.trending")} subtitle={t("home.v2.trendingSub")} products={trending} href="/sale-stream" linkLabel={t("home.v2.viewAll")} />
      ) : (
        <ProductRow id="new-arrivals" title={t("home.v2.newArrivals")} subtitle={t("home.v2.newArrivalsSub")} products={(d.featured ?? []).slice(0, 10)} href="/products?sort_by=newest" linkLabel={t("home.v2.viewAll")} />
      )}
      <div className="pt-8" />

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
            <Link key={r.id} href={`/products?retailer_id=${r.id}`} className="flex items-start gap-3 rounded-xl border bg-white p-4 hover:border-brand">
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
