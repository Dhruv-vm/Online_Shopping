"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  BadgeCheck,
  Bot,
  Gavel,
  LineChart,
  Store,
  Target,
  Users,
} from "lucide-react";
import { ProductCard } from "@/components/catalogue/product-card";
import { ProductImage } from "@/components/catalogue/product-image";
import { Rail, Section, SkeletonCards } from "@/components/home/section";
import { AppPromo } from "@/components/home/app-promo";
import { BasketEdit, CampaignRow, DealsBanner, imageByCategory, ProductRow, ServiceStrip, ShopByCategory, StorefrontHero } from "@/components/home/storefront";
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
    <Link href={`/products/${e.product_id}`} className="group overflow-hidden p-2.5 rounded-card bg-white shadow-card ring-1 ring-black/[0.04] transition-[transform,box-shadow] duration-base ease-out hover:-translate-y-1 hover:shadow-card-hover">
      <div className="relative aspect-[4/3] overflow-hidden rounded-[0.9rem] bg-[#F6F4EF]">
        <ProductImage src={e.image_url} alt={e.product_name} />
        <span className="absolute left-2.5 top-2.5 rounded-md bg-brand-yellow px-2 py-[3px] text-[11px] font-extrabold leading-none text-ink">{t(`stream.${e.event_type}`)}</span>
      </div>
      <div className="space-y-1 px-1.5 pb-1 pt-3 text-sm">
        <p className="line-clamp-2 text-[13.5px] font-bold leading-snug">{e.product_name}</p>
        <p className="text-xs text-muted-foreground">{e.retailer_name}</p>
        <p>
          <span className="font-bold">{money(e.deal_price_paise)}</span>{" "}
          {e.old_price_paise > e.deal_price_paise && <span className="text-xs text-muted-foreground line-through">{money(e.old_price_paise)}</span>}
          {e.discount_pct > 0 && <span className="ml-1 text-xs font-bold text-brand-green-logo">−{Math.round(e.discount_pct)}%</span>}
        </p>
        <p className="text-[11px] text-muted-foreground">
          {t("common.timeLeft")}: <Countdown seconds={e.seconds_remaining} /> · {t("common.onlyLeft", { n: e.stock_remaining })}
        </p>
      </div>
    </Link>
  );
}

export default function HomePage() {
  const { t } = useI18n();
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
  // "Trending" only when the Sale Stream reports real hot sellers.
  const trending = useMemo(() => {
    const ids = new Set((d.stream ?? []).filter((e) => e.event_type === "HOT_SELLER").map((e) => e.product_id));
    return (d.catalogue ?? []).filter((p) => ids.has(p.id)).slice(0, 5);
  }, [d.stream, d.catalogue]);
  const drops = (d.stream ?? []).filter((e) => e.event_type === "PRICE_DROP");

  return (
    <div>
      <StorefrontHero products={d.catalogue} retailers={d.retailers} stats={stats} />
      <ServiceStrip />
      {d.categories && d.catalogue ? (
        <ShopByCategory categories={d.categories} images={catImages} />
      ) : (
        <div className="container-page pt-12"><SkeletonCards /></div>
      )}
      {d.catalogue && <DealsBanner deals={d.stream ?? []} products={d.catalogue} />}
      {d.categories && d.catalogue && <BasketEdit categories={d.categories} images={catImages} />}
      {trending.length > 0 ? (
        <ProductRow id="trending" title={t("home.v2.trending")} subtitle={t("home.v2.trendingSub")} products={trending} href="/sale-stream" linkLabel={t("home.v2.viewAll")} />
      ) : (
        <ProductRow id="new-arrivals" title={t("home.v2.newArrivals")} subtitle={t("home.v2.newArrivalsSub")} products={(d.featured ?? []).slice(0, 5)} href="/products?sort_by=newest" linkLabel={t("home.v2.viewAll")} />
      )}
      {d.catalogue && <CampaignRow images={catImages} />}
      <div className="pt-8" />

      <Section id="brands" title={t("home.brands.title")} subtitle={t("home.brands.subtitle")}>
        <div className="flex flex-wrap gap-2">
          {brands.map((b) => (
            <Link key={b} href={`/search?q=${encodeURIComponent(b)}`} className="press rounded-full bg-white px-4 py-2 text-sm font-semibold shadow-card ring-1 ring-black/[0.04] hover:bg-ink hover:text-white">{b}</Link>
          ))}
        </div>
        <p className="mt-3 text-xs text-muted-foreground">{t("home.brands.note")}</p>
      </Section>

      <Section id="partners" title={t("home.partners.title")} subtitle={t("home.partners.subtitle")} href="/retailers" linkLabel={t("common.viewAll")} tone="tint">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {(d.retailers ?? []).slice(0, 8).map((r) => (
            <Link key={r.id} href={`/products?retailer_id=${r.id}`} className="flex items-start gap-3 p-4 rounded-card bg-white shadow-card ring-1 ring-black/[0.04] transition-[transform,box-shadow] duration-base ease-out hover:-translate-y-1 hover:shadow-card-hover">
              <span className="flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-full bg-brand-light text-ink">
                {r.logo_url ? <ProductImage src={r.logo_url} alt={r.name} /> : <Store className="h-5 w-5" />}
              </span>
              <span className="min-w-0">
                <span className="flex items-center gap-1 font-semibold"><span className="truncate">{r.name}</span><BadgeCheck className="h-4 w-4 shrink-0 text-brand-green-logo" aria-label={t("home.partners.verified")} /></span>
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
              <li key={p.id} className="flex items-center justify-between rounded-card bg-white p-4 text-sm shadow-card ring-1 ring-black/[0.04]">
                <span>
                  <span className="block font-semibold">{p.display_name}</span>
                  <span className="text-xs text-muted-foreground">{t("requests.shoppers", { n: p.unique_users_count })}{p.pincode ? ` · PIN ${p.pincode}` : ""}</span>
                </span>
                <Link href={`/search?q=${encodeURIComponent(p.display_name)}`} className="press rounded-full bg-brand-yellow px-3 py-1.5 text-xs font-bold text-ink hover:bg-brand-yellow-dark">{t("home.demand.cta")}</Link>
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
            <Link key={k} href={href} className="group rounded-card bg-white/[0.07] p-6 ring-1 ring-white/10 transition-colors duration-base hover:bg-white/[0.12]">
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
            <Link key={k} href="/missions" className="flex items-center gap-3 p-4 rounded-card bg-white shadow-card ring-1 ring-black/[0.04] transition-[transform,box-shadow] duration-base ease-out hover:-translate-y-1 hover:shadow-card-hover">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-yellow"><Target className="h-5 w-5 text-ink" /></span>
              <span className="text-sm font-semibold">{t(k)}</span>
            </Link>
          ))}
        </div>
      </Section>

      {recent.length > 0 && (
        <Section id="recent" title={t("home.recent.title")}>
          <Rail>
            {recent.map((p) => (
              <Link key={p.slug} href={`/products/${p.slug}`} className="overflow-hidden p-2.5 rounded-card bg-white shadow-card ring-1 ring-black/[0.04] transition-[transform,box-shadow] duration-base ease-out hover:-translate-y-1 hover:shadow-card-hover">
                <div className="aspect-square overflow-hidden rounded-[0.9rem] bg-[#F6F4EF]"><ProductImage src={p.image} alt={p.name} /></div>
                <div className="px-1.5 pb-1 pt-3 text-sm">
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

      <AppPromo />
    </div>
  );
}
