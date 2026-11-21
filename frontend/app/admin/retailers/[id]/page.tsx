"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  BarChart3,
  Calendar,
  CheckCircle2,
  ChevronRight,
  DollarSign,
  FileSpreadsheet,
  IndianRupee,
  Layers,
  Loader2,
  Package,
  PackageCheck,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  ShoppingBag,
  Store,
  TrendingDown,
  TrendingUp,
  Wallet,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiClient } from "@/lib/api/client";
import { formatPrice } from "@/lib/utils";
import type {
  AdminRetailerDetailResponse,
  AdminRetailerSalesAnalyticsResponse,
} from "@/types";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function AdminRetailerAnalyticsPage({ params }: PageProps) {
  const resolvedParams = use(params);
  const retailerId = resolvedParams.id;

  const [analytics, setAnalytics] =
    useState<AdminRetailerSalesAnalyticsResponse | null>(null);
  const [retailer, setRetailer] =
    useState<AdminRetailerDetailResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const [analyticsData, retailerData] = await Promise.all([
        apiClient.getAdminRetailerAnalytics(retailerId),
        apiClient.getAdminRetailer(retailerId),
      ]);
      setAnalytics(analyticsData);
      setRetailer(retailerData);
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof Error
          ? err.message
          : "Failed to load store sales analytics."
      );
    } finally {
      setIsLoading(false);
    }
  }, [retailerId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "VERIFIED":
        return (
          <Badge className="bg-emerald-600 text-white font-medium flex items-center gap-1">
            <ShieldCheck className="h-3 w-3" />
            Verified
          </Badge>
        );
      case "PENDING":
        return (
          <Badge className="bg-amber-500 text-white font-medium flex items-center gap-1">
            <RefreshCw className="h-3 w-3 animate-spin" />
            Pending Review
          </Badge>
        );
      case "SUSPENDED":
        return (
          <Badge variant="destructive" className="font-medium flex items-center gap-1">
            <ShieldAlert className="h-3 w-3" />
            Suspended
          </Badge>
        );
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Navigation Breadcrumb */}
      <nav className="flex items-center space-x-2 text-xs text-muted-foreground">
        <Link href="/admin" className="hover:text-foreground">
          Admin
        </Link>
        <ChevronRight className="h-3.5 w-3.5" />
        <Link href="/admin/retailers" className="hover:text-foreground">
          Retailers
        </Link>
        <ChevronRight className="h-3.5 w-3.5" />
        <span className="truncate max-w-[200px] text-foreground font-medium">
          {analytics?.retailer_name || "Store Sales Analytics"}
        </span>
      </nav>

      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b pb-5">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <Link href="/admin/retailers">
              <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                <ArrowLeft className="h-4 w-4" />
              </Button>
            </Link>
            <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
              <Store className="h-6 w-6 text-purple-600" />
              {analytics?.retailer_name || "Store Sales & Performance"}
            </h1>
            {analytics && getStatusBadge(analytics.verification_status)}
            {analytics?.is_active ? (
              <Badge variant="outline" className="text-emerald-700 border-emerald-600/40 text-[10px]">
                Active Merchant
              </Badge>
            ) : (
              <Badge variant="outline" className="text-muted-foreground border-border text-[10px]">
                Inactive
              </Badge>
            )}
          </div>
          <p className="text-xs text-muted-foreground pl-11">
            Real-time financial reconciliation and product-level sales metrics computed directly from PostgreSQL ledger.
          </p>
        </div>

        <div className="flex items-center gap-2 pl-11 sm:pl-0">
          <Button
            variant="outline"
            size="sm"
            onClick={loadData}
            disabled={isLoading}
            className="h-8 text-xs gap-1.5"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`} />
            Refresh Ledger
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="py-24 text-center text-sm text-muted-foreground">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-2 border-solid border-purple-600 border-r-transparent mb-3" />
          <p className="font-medium text-foreground">Computing authoritative sales ledger from PostgreSQL...</p>
        </div>
      ) : errorMsg || !analytics ? (
        <div className="text-center py-20 bg-destructive/10 rounded-xl p-8 border border-destructive/20 max-w-lg mx-auto">
          <p className="text-destructive font-medium mb-3">
            {errorMsg || "Store analytics could not be retrieved."}
          </p>
          <Link href="/admin/retailers">
            <Button variant="outline" size="sm">
              <ArrowLeft className="h-4 w-4 mr-1.5" />
              Return to Retailer Directory
            </Button>
          </Link>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Store Metadata Card */}
          {retailer && (
            <Card className="bg-muted/30 border">
              <CardContent className="p-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
                <div>
                  <span className="text-muted-foreground font-medium">Business Address:</span>
                  <div className="text-foreground font-semibold mt-0.5">
                    {retailer.business_address || "Not specified"}
                  </div>
                </div>
                <div>
                  <span className="text-muted-foreground font-medium">State / Region:</span>
                  <div className="text-foreground font-semibold mt-0.5">
                    {retailer.state ? `${retailer.state} (India)` : "—"}
                  </div>
                </div>
                <div>
                  <span className="text-muted-foreground font-medium">Owner / Account Contact:</span>
                  <div className="text-foreground font-semibold mt-0.5">
                    {retailer.owner_name || retailer.contact_email || "—"}
                  </div>
                  <div className="text-muted-foreground text-[11px]">
                    {retailer.owner_email || retailer.contact_phone || "—"}
                  </div>
                </div>
                <div>
                  <span className="text-muted-foreground font-medium">Merchant Rating & Compliance:</span>
                  <div className="text-foreground font-semibold mt-0.5 flex items-center gap-1.5">
                    <span>★ {retailer.rating.toFixed(1)} / 5.0</span>
                    <span>•</span>
                    <span>{retailer.documents.length} verified docs</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* 4 Primary Financial KPI Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card className="border bg-card shadow-xs">
              <CardContent className="p-4 flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium text-muted-foreground">Total Orders Placed</p>
                  <p className="text-2xl font-bold text-foreground mt-1">
                    {analytics.total_orders.toLocaleString()}
                  </p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    Multi-retailer & single orders
                  </p>
                </div>
                <div className="h-10 w-10 rounded-xl bg-purple-100 text-purple-700 dark:bg-purple-950 dark:text-purple-300 flex items-center justify-center">
                  <ShoppingBag className="h-5 w-5" />
                </div>
              </CardContent>
            </Card>

            <Card className="border bg-card shadow-xs">
              <CardContent className="p-4 flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium text-muted-foreground">Total Units Sold</p>
                  <p className="text-2xl font-bold text-foreground mt-1">
                    {analytics.total_units_sold.toLocaleString()}
                  </p>
                  <p className="text-[11px] text-emerald-600 font-medium mt-0.5 flex items-center gap-1">
                    <CheckCircle2 className="h-3 w-3" />
                    Fulfilled items
                  </p>
                </div>
                <div className="h-10 w-10 rounded-xl bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300 flex items-center justify-center">
                  <PackageCheck className="h-5 w-5" />
                </div>
              </CardContent>
            </Card>

            <Card className="border bg-card shadow-xs">
              <CardContent className="p-4 flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium text-muted-foreground">Gross Merchandise Value (GMV)</p>
                  <p className="text-2xl font-bold text-foreground mt-1">
                    {formatPrice(analytics.gross_merchandise_value_paise, analytics.currency)}
                  </p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    Total order value before refunds
                  </p>
                </div>
                <div className="h-10 w-10 rounded-xl bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300 flex items-center justify-center">
                  <TrendingUp className="h-5 w-5" />
                </div>
              </CardContent>
            </Card>

            <Card className="border bg-card shadow-xs">
              <CardContent className="p-4 flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium text-muted-foreground">Net Sales Revenue</p>
                  <p className="text-2xl font-bold text-emerald-700 dark:text-emerald-400 mt-1">
                    {formatPrice(analytics.net_sales_paise, analytics.currency)}
                  </p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    {analytics.refunded_amount_paise > 0
                      ? `After ${formatPrice(analytics.refunded_amount_paise, analytics.currency)} refunds`
                      : "Zero refunds recorded"}
                  </p>
                </div>
                <div className="h-10 w-10 rounded-xl bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300 flex items-center justify-center">
                  <Wallet className="h-5 w-5" />
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Product-Level Sales Table */}
          <div className="rounded-xl border bg-card shadow-xs overflow-hidden">
            <div className="p-4 border-b flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <h3 className="font-bold text-sm text-foreground flex items-center gap-2">
                  <BarChart3 className="h-4 w-4 text-purple-600" />
                  Product-Level Sales Breakdown ({analytics.product_sales.length} items)
                </h3>
                <p className="text-xs text-muted-foreground">
                  Individual item sales volume, unit selling prices, gross receipts, and return adjustments.
                </p>
              </div>
            </div>

            {analytics.product_sales.length === 0 ? (
              <div className="py-16 text-center text-xs text-muted-foreground">
                <Package className="h-8 w-8 mx-auto mb-2 text-muted-foreground/60" />
                <p className="font-semibold text-foreground text-sm">No confirmed sales yet</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Sales metrics will populate here automatically as customers purchase this retailer&apos;s listings.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-muted/50 border-b text-muted-foreground font-semibold">
                    <tr>
                      <th className="px-4 py-3">Product Title & Variant</th>
                      <th className="px-4 py-3">SKU</th>
                      <th className="px-4 py-3 text-right">Units Sold</th>
                      <th className="px-4 py-3 text-right">Selling Price</th>
                      <th className="px-4 py-3 text-right">Gross Revenue</th>
                      <th className="px-4 py-3 text-right">Refunds</th>
                      <th className="px-4 py-3 text-right">Net Sales</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {analytics.product_sales.map((item) => (
                      <tr key={item.variant_id} className="hover:bg-muted/30 transition-colors">
                        <td className="px-4 py-3">
                          <div className="font-semibold text-foreground text-sm">
                            {item.product_name}
                          </div>
                          <div className="text-[11px] text-muted-foreground">
                            Variant: {item.variant_name}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-muted-foreground font-mono text-[11px]">
                          {item.sku || "—"}
                        </td>
                        <td className="px-4 py-3 text-right font-semibold text-foreground">
                          {item.quantity_sold.toLocaleString()}
                        </td>
                        <td className="px-4 py-3 text-right text-foreground">
                          {formatPrice(item.selling_price_paise, analytics.currency)}
                        </td>
                        <td className="px-4 py-3 text-right font-medium text-foreground">
                          {formatPrice(item.gross_revenue_paise, analytics.currency)}
                        </td>
                        <td className="px-4 py-3 text-right text-muted-foreground">
                          {item.refund_quantity > 0 ? (
                            <span className="text-rose-600 font-medium">
                              -{formatPrice(item.refund_amount_paise, analytics.currency)} ({item.refund_quantity})
                            </span>
                          ) : (
                            "—"
                          )}
                        </td>
                        <td className="px-4 py-3 text-right font-bold text-emerald-700 dark:text-emerald-400">
                          {formatPrice(item.net_sales_paise, analytics.currency)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot className="bg-muted/40 font-bold border-t">
                    <tr>
                      <td colSpan={2} className="px-4 py-3 text-foreground">
                        Total Ledger Summary
                      </td>
                      <td className="px-4 py-3 text-right text-foreground">
                        {analytics.total_units_sold.toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-right">—</td>
                      <td className="px-4 py-3 text-right text-foreground">
                        {formatPrice(analytics.gross_merchandise_value_paise, analytics.currency)}
                      </td>
                      <td className="px-4 py-3 text-right text-rose-600">
                        {analytics.refunded_amount_paise > 0
                          ? `-${formatPrice(analytics.refunded_amount_paise, analytics.currency)}`
                          : "—"}
                      </td>
                      <td className="px-4 py-3 text-right text-emerald-700 dark:text-emerald-400">
                        {formatPrice(analytics.net_sales_paise, analytics.currency)}
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
