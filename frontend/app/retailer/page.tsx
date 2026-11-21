"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, IndianRupee, Layers, Package, PlusCircle, Power, RefreshCw, ShoppingCart, Store, TrendingUp } from "lucide-react";
import { BasketLoader } from "@/components/brand/basket-loader";
import { EmptyState, Kpi, Notice, PageHeader } from "@/components/portal/kpi";
import { apiClient } from "@/lib/api/client";
import { errorMessage } from "@/lib/i18n/errors";
import { useI18n } from "@/lib/i18n/i18n-context";
import type { RetailerAnalyticsResponse, RetailerOverview, RetailerProfile } from "@/types";
import { useLiveUpdates } from "@/lib/realtime";

const IN_FLIGHT = ["CONFIRMED", "PROCESSING", "PACKED"];

export default function RetailerDashboardPage() {
  const { t, money, number } = useI18n();
  const [overview, setOverview] = useState<RetailerOverview | null>(null);
  const [profile, setProfile] = useState<RetailerProfile | null>(null);
  const [analytics, setAnalytics] = useState<RetailerAnalyticsResponse | null>(null);
  const [notice, setNotice] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState(false);

  const load = useCallback(async (opts?: { quiet?: boolean }) => {
    if (!opts?.quiet) setLoading(true);
    try {
      const [o, p, a] = await Promise.all([
        apiClient.getRetailerOverview(),
        apiClient.getRetailerProfile(),
        apiClient.getRetailerAnalytics().catch(() => null),
      ]);
      setOverview(o);
      setProfile(p);
      setAnalytics(a);
    } catch (err) {
      setNotice({ kind: "error", text: errorMessage(err, t) });
    } finally {
      setLoading(false);
    }
  }, [t]);
  useLiveUpdates(["order.", "payment.", "fulfilment.", "auction.", "demand.", "negotiation.", "group_buy.", "exchange."], () => void load({ quiet: true }));

  useEffect(() => {
    load();
  }, [load]);

  const toggleOpen = async () => {
    if (!profile) return;
    setToggling(true);
    try {
      const updated = await apiClient.updateRetailerProfile({ is_open: !profile.is_open });
      setProfile(updated);
      setNotice({ kind: "ok", text: updated.is_open ? t("retailer.dash.nowOpen") : t("retailer.dash.nowClosed") });
    } catch (err) {
      setNotice({ kind: "error", text: errorMessage(err, t) });
    } finally {
      setToggling(false);
    }
  };

  if (loading && !overview) return <BasketLoader />;
  if (!overview || !profile) return notice ? <Notice kind="error">{notice.text}</Notice> : null;

  const verified = profile.verification_status === "VERIFIED";
  const inFlight = IN_FLIGHT.reduce((s, k) => s + (analytics?.orders_by_status?.[k] ?? 0), 0);

  return (
    <div>
      <PageHeader
        title={profile.name}
        subtitle={t("retailer.dash.subtitle")}
        actions={
          <>
            <button type="button" onClick={() => void load()} className="inline-flex items-center gap-1.5 rounded-lg border bg-white px-3 py-2 text-sm">
              <RefreshCw className="h-4 w-4" /> {t("common.refresh")}
            </button>
            {verified && (
              <button
                type="button"
                onClick={toggleOpen}
                disabled={toggling}
                className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-semibold text-white disabled:opacity-60 ${profile.is_open ? "bg-amber-600" : "bg-brand"}`}
              >
                <Power className="h-4 w-4" /> {profile.is_open ? t("retailer.dash.pause") : t("retailer.dash.open")}
              </button>
            )}
          </>
        }
      />
      {notice && <Notice kind={notice.kind}>{notice.text}</Notice>}

      {(overview.low_stock_alerts > 0 || overview.out_of_stock_alerts > 0) && (
        <div className="mb-4 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>
            {t("retailer.dash.stockAlert", { low: overview.low_stock_alerts, out: overview.out_of_stock_alerts })}{" "}
            <Link href="/retailer/inventory" className="font-semibold underline">{t("retailer.nav.inventory")}</Link>
          </span>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi
          label={t("retailer.dash.storeStatus")}
          value={verified ? (profile.is_open ? t("retailer.banner.open") : t("retailer.banner.closed")) : t(`retailer.status.${profile.verification_status}.title`)}
          icon={<Store className="h-4 w-4" />}
          tone={verified && profile.is_open ? "good" : "warn"}
        />
        <Kpi label={t("retailer.dash.activeListings")} value={`${number(overview.active_listings)} / ${number(overview.total_listings)}`} icon={<Layers className="h-4 w-4" />} />
        <Kpi label={t("retailer.dash.stockOnHand")} value={number(overview.total_inventory_units)} hint={t("retailer.dash.stockHint")} icon={<Package className="h-4 w-4" />} />
        <Kpi label={t("retailer.dash.toFulfil")} value={number(inFlight)} hint={t("retailer.dash.toFulfilHint")} icon={<ShoppingCart className="h-4 w-4" />} tone={inFlight > 0 ? "warn" : "default"} />
        <Kpi label={t("analytics.grossSales")} value={money(analytics?.gross_sales_paise ?? 0)} hint={t("analytics.grossSalesHint")} icon={<IndianRupee className="h-4 w-4" />} />
        <Kpi label={t("analytics.settledRevenue")} value={money(analytics?.settled_revenue_paise ?? 0)} hint={t("analytics.settledHint")} icon={<IndianRupee className="h-4 w-4" />} />
        <Kpi label={t("analytics.paidOrders")} value={number(analytics?.paid_orders ?? 0)} hint={t("analytics.pendingPaymentHint", { n: analytics?.pending_payment_orders ?? 0 })} icon={<ShoppingCart className="h-4 w-4" />} />
        <Kpi label={t("analytics.aov")} value={money(analytics?.average_order_value_paise ?? 0)} hint={t("analytics.aovHint")} icon={<TrendingUp className="h-4 w-4" />} />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <section className="rounded-xl border bg-white p-5">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-semibold">{t("analytics.topProducts")}</h2>
            <Link href="/retailer/analytics" className="text-sm text-brand underline">{t("common.viewAll")}</Link>
          </div>
          {analytics && analytics.top_selling_products.length > 0 ? (
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-muted-foreground">
                <tr>
                  <th className="py-2">{t("common.product")}</th>
                  <th className="py-2 text-right">{t("analytics.unitsSold")}</th>
                  <th className="py-2 text-right">{t("analytics.revenue")}</th>
                </tr>
              </thead>
              <tbody>
                {analytics.top_selling_products.slice(0, 5).map((p) => (
                  <tr key={`${p.listing_id}-${p.variant_sku}`} className="border-t">
                    <td className="py-2">{p.product_name}</td>
                    <td className="py-2 text-right">{number(p.units_sold)}</td>
                    <td className="py-2 text-right">{money(p.revenue_paise)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <EmptyState title={t("analytics.noSales")} body={t("analytics.noSalesBody")} />
          )}
        </section>

        <section className="space-y-3">
          {[
            { href: "/retailer/listings/new", k: "retailer.nav.addProduct", icon: PlusCircle },
            { href: "/retailer/orders", k: "retailer.nav.orders", icon: ShoppingCart },
            { href: "/retailer/inventory", k: "retailer.nav.inventory", icon: Package },
            { href: "/retailer/offers", k: "retailer.nav.offers", icon: IndianRupee },
          ].map(({ href, k, icon: Icon }) => (
            <Link key={href} href={href} className="flex items-center gap-3 rounded-xl border bg-white p-4 hover:border-brand">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-light text-brand-dark"><Icon className="h-5 w-5" /></span>
              <span className="font-medium">{t(k)}</span>
            </Link>
          ))}
          <div className="rounded-xl border bg-white p-4 text-sm">
            <p className="font-semibold">{t("retailer.dash.storeDetails")}</p>
            <dl className="mt-2 space-y-1 text-muted-foreground">
              <div>{profile.business_address ?? "—"}</div>
              <div>{profile.contact_phone ?? "—"} · {profile.contact_email ?? "—"}</div>
              <div>GSTIN: {profile.gstin ?? t("retailer.dash.gstinMissing")}</div>
            </dl>
            <Link href="/retailer/profile" className="mt-2 inline-block text-brand underline">{t("retailer.dash.editProfile")}</Link>
          </div>
        </section>
      </div>
    </div>
  );
}
