"use client";

import { useEffect, useState, useCallback } from "react";
import {
  BarChart3,
  TrendingUp,
  DollarSign,
  ShoppingCart,
  Package,
  AlertTriangle,
  RefreshCw,
  CheckCircle,
  XCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api/client";
import type { RetailerAnalyticsResponse } from "@/types";

export default function RetailerAnalyticsPage() {
  const [data, setData] = useState<RetailerAnalyticsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const loadAnalytics = useCallback(async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const res = await apiClient.getRetailerAnalytics();
      setData(res);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to load store sales analytics.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAnalytics();
  }, [loadAnalytics]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <BarChart3 className="h-6 w-6 text-blue-600" />
            Store Sales Analytics & Performance
          </h1>
          <p className="text-sm text-muted-foreground">
            Live metrics on store revenue, order fulfillment velocity, top performing catalogue items, and inventory health.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={loadAnalytics}
          disabled={isLoading}
          className="gap-2"
        >
          <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
          Refresh Metrics
        </Button>
      </div>

      {errorMsg && (
        <div className="p-4 rounded-xl border border-red-500/30 bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 text-sm flex items-center gap-3">
          <AlertTriangle className="h-5 w-5 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {isLoading || !data ? (
        <div className="p-16 text-center text-muted-foreground space-y-3 border rounded-xl bg-card">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-blue-600 border-r-transparent align-[-0.125em]" />
          <p className="text-sm">Aggregating transactional analytics from database...</p>
        </div>
      ) : (
        <>
          {/* Top 4 KPI Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="rounded-xl border bg-card p-5 shadow-xs space-y-2">
              <div className="flex items-center justify-between text-muted-foreground">
                <span className="text-xs font-semibold uppercase tracking-wider">Gross Sales</span>
                <DollarSign className="h-4 w-4 text-emerald-600" />
              </div>
              <div className="text-2xl font-bold text-foreground font-mono">
                ₹{(data.total_revenue_paise / 100).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
              </div>
              <p className="text-[11px] text-muted-foreground">Settled across confirmed customer orders</p>
            </div>

            <div className="rounded-xl border bg-card p-5 shadow-xs space-y-2">
              <div className="flex items-center justify-between text-muted-foreground">
                <span className="text-xs font-semibold uppercase tracking-wider">Fulfilled Orders</span>
                <ShoppingCart className="h-4 w-4 text-blue-600" />
              </div>
              <div className="text-2xl font-bold text-foreground font-mono">
                {data.total_orders}
              </div>
              <p className="text-[11px] text-muted-foreground">Distinct customer purchases</p>
            </div>

            <div className="rounded-xl border bg-card p-5 shadow-xs space-y-2">
              <div className="flex items-center justify-between text-muted-foreground">
                <span className="text-xs font-semibold uppercase tracking-wider">Units Dispatched</span>
                <Package className="h-4 w-4 text-purple-600" />
              </div>
              <div className="text-2xl font-bold text-foreground font-mono">
                {data.total_units_sold}
              </div>
              <p className="text-[11px] text-muted-foreground">Individual items sold</p>
            </div>

            <div className="rounded-xl border bg-card p-5 shadow-xs space-y-2">
              <div className="flex items-center justify-between text-muted-foreground">
                <span className="text-xs font-semibold uppercase tracking-wider">Avg Order Value</span>
                <TrendingUp className="h-4 w-4 text-amber-600" />
              </div>
              <div className="text-2xl font-bold text-foreground font-mono">
                ₹{(data.average_order_value_paise / 100).toFixed(2)}
              </div>
              <p className="text-[11px] text-muted-foreground">Average store basket ticket</p>
            </div>
          </div>

          {/* Section: Stock Health & Orders Breakdown */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Orders by Status */}
            <div className="rounded-xl border bg-card p-5 shadow-xs space-y-4">
              <div className="font-bold text-foreground text-sm flex items-center justify-between">
                <span>Orders by Fulfilment Stage</span>
                <Badge variant="outline" className="text-xs font-normal">Live Pipeline</Badge>
              </div>
              <div className="space-y-3">
                {Object.entries(data.orders_by_status).length === 0 ? (
                  <p className="text-xs text-muted-foreground">No orders in pipeline.</p>
                ) : (
                  Object.entries(data.orders_by_status).map(([status, count]) => {
                    const percentage = Math.min(100, Math.round((count / Math.max(1, data.total_orders)) * 100));
                    return (
                      <div key={status} className="space-y-1">
                        <div className="flex justify-between text-xs">
                          <span className="font-semibold text-foreground capitalize">
                            {status.replace(/_/g, " ").toLowerCase()}
                          </span>
                          <span className="font-mono text-muted-foreground">{count} orders ({percentage}%)</span>
                        </div>
                        <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
                          <div
                            className={`h-full rounded-full ${
                              status === "DELIVERED"
                                ? "bg-emerald-500"
                                : status === "SHIPPED"
                                ? "bg-indigo-500"
                                : status === "PACKED"
                                ? "bg-purple-500"
                                : status === "CANCELLED"
                                ? "bg-red-500"
                                : "bg-blue-500"
                            }`}
                            style={{ width: `${percentage}%` }}
                          />
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>

            {/* Inventory Health Summary */}
            <div className="rounded-xl border bg-card p-5 shadow-xs space-y-4">
              <div className="font-bold text-foreground text-sm flex items-center justify-between">
                <span>Inventory Health & Alerts</span>
                <Badge variant="outline" className="text-xs font-normal">Realtime</Badge>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div className="p-4 rounded-xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 text-center space-y-1">
                  <CheckCircle className="h-5 w-5 text-emerald-600 mx-auto" />
                  <div className="text-2xl font-bold font-mono text-emerald-700 dark:text-emerald-300">
                    {data.in_stock_count}
                  </div>
                  <div className="text-[11px] font-semibold text-emerald-800 dark:text-emerald-200 uppercase">
                    In Stock
                  </div>
                </div>

                <div className="p-4 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 text-center space-y-1">
                  <AlertTriangle className="h-5 w-5 text-amber-600 mx-auto" />
                  <div className="text-2xl font-bold font-mono text-amber-700 dark:text-amber-300">
                    {data.low_stock_count}
                  </div>
                  <div className="text-[11px] font-semibold text-amber-800 dark:text-amber-200 uppercase">
                    Low Stock
                  </div>
                </div>

                <div className="p-4 rounded-xl bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 text-center space-y-1">
                  <XCircle className="h-5 w-5 text-red-600 mx-auto" />
                  <div className="text-2xl font-bold font-mono text-red-700 dark:text-red-300">
                    {data.out_of_stock_count}
                  </div>
                  <div className="text-[11px] font-semibold text-red-800 dark:text-red-200 uppercase">
                    Out of Stock
                  </div>
                </div>
              </div>
              <p className="text-[11px] text-muted-foreground">
                Low stock alerts trigger when available stock drops to or below your configured minimum threshold.
              </p>
            </div>
          </div>

          {/* Top Selling Products Table */}
          <div className="rounded-xl border bg-card p-5 shadow-xs space-y-3">
            <div className="font-bold text-foreground text-sm">Top Selling Store Products</div>
            {data.top_selling_products.length === 0 ? (
              <p className="text-xs text-muted-foreground py-4 text-center">
                Product sales ranking will appear as customer orders are confirmed.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b text-muted-foreground text-left">
                      <th className="py-2 px-3">Product Name</th>
                      <th className="py-2 px-3 font-mono">SKU</th>
                      <th className="py-2 px-3 text-right">Units Sold</th>
                      <th className="py-2 px-3 text-right">Revenue</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {data.top_selling_products.map((item, idx) => (
                      <tr key={item.listing_id || idx} className="hover:bg-muted/40 transition-colors">
                        <td className="py-2.5 px-3 font-semibold text-foreground">{item.product_name}</td>
                        <td className="py-2.5 px-3 font-mono text-muted-foreground">{item.variant_sku}</td>
                        <td className="py-2.5 px-3 text-right font-mono font-bold">{item.units_sold}</td>
                        <td className="py-2.5 px-3 text-right font-mono font-bold text-emerald-600">
                          ₹{(item.revenue_paise / 100).toFixed(2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
