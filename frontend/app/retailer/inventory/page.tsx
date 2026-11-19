"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  Boxes,
  Search,
  RefreshCw,
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  X,
  SlidersHorizontal,
  ArrowRight,
  TrendingUp,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiClient, ApiClientError } from "@/lib/api/client";
import type { RetailerInventoryDashboard, RetailerInventoryItem } from "@/types";

export default function RetailerInventoryPage() {
  const [dashboard, setDashboard] = useState<RetailerInventoryDashboard | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Adjustment Modal State
  const [adjustingItem, setAdjustingItem] = useState<RetailerInventoryItem | null>(null);
  const [adjustType, setAdjustType] = useState<"SET" | "DELTA">("SET");
  const [adjustQuantity, setAdjustQuantity] = useState("");
  const [adjustThreshold, setAdjustThreshold] = useState("");
  const [adjustReason, setAdjustReason] = useState("");
  const [isSubmittingAdjust, setIsSubmittingAdjust] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  const loadInventory = useCallback(async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const data = await apiClient.getRetailerInventory({
        search: searchQuery.trim() || undefined,
        status_filter: statusFilter === "ALL" ? undefined : statusFilter,
      });
      setDashboard(data);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to load inventory dashboard.");
    } finally {
      setIsLoading(false);
    }
  }, [searchQuery, statusFilter]);

  useEffect(() => {
    loadInventory();
  }, [loadInventory]);

  const openAdjustModal = (item: RetailerInventoryItem) => {
    setAdjustingItem(item);
    setAdjustType("SET");
    setAdjustQuantity(String(item.on_hand_quantity));
    setAdjustThreshold(String(item.low_stock_threshold));
    setAdjustReason("");
    setModalError(null);
  };

  const closeAdjustModal = () => {
    setAdjustingItem(null);
    setModalError(null);
  };

  const handleAdjustSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!adjustingItem) return;

    const qty = parseInt(adjustQuantity, 10);
    const thresh = parseInt(adjustThreshold, 10);

    if (isNaN(qty)) {
      setModalError("Please enter a valid quantity.");
      return;
    }
    if (adjustType === "SET" && qty < 0) {
      setModalError("Quantity cannot be negative for exact SET adjustments.");
      return;
    }
    if (adjustType === "SET" && qty < adjustingItem.reserved_quantity) {
      setModalError(
        `Cannot reduce stock below active reserved holds (${adjustingItem.reserved_quantity} units).`
      );
      return;
    }

    setIsSubmittingAdjust(true);
    setModalError(null);

    try {
      const updated = await apiClient.adjustRetailerInventory(adjustingItem.listing_id, {
        adjustment_type: adjustType,
        quantity: qty,
        low_stock_threshold: isNaN(thresh) ? undefined : thresh,
        reason: adjustReason.trim() || undefined,
      });

      setDashboard((prev) => {
        if (!prev) return null;
        return {
          ...prev,
          items: prev.items.map((i) => (i.listing_id === updated.listing_id ? updated : i)),
        };
      });

      setSuccessMsg(
        `Inventory for "${updated.product_name}" updated to ${updated.on_hand_quantity} units.`
      );
      closeAdjustModal();
      // Reload stats
      loadInventory();
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setModalError(err.message);
      } else {
        setModalError(err instanceof Error ? err.message : "Failed to adjust stock.");
      }
    } finally {
      setIsSubmittingAdjust(false);
    }
  };

  const summary = dashboard?.summary;

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Boxes className="h-6 w-6 text-emerald-600" />
            Stock & Inventory Console
          </h1>
          <p className="text-sm text-muted-foreground">
            Monitor real-time warehouse on-hand stock, active checkout reservation holds, and low-stock alerts.
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <Button
            variant="outline"
            size="sm"
            onClick={loadInventory}
            disabled={isLoading}
            className="gap-2"
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </Button>

          <Link href="/retailer/listings">
            <Button size="sm" variant="outline" className="gap-2">
              View All Listings <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </Link>
        </div>
      </div>

      {/* Messages */}
      {errorMsg && (
        <div className="p-3.5 rounded-lg border border-red-500/30 bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 text-sm flex items-center gap-2">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}
      {successMsg && (
        <div className="p-3.5 rounded-lg border border-emerald-500/30 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 text-sm flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 shrink-0" />
            <span>{successMsg}</span>
          </div>
          <button onClick={() => setSuccessMsg(null)} className="text-xs hover:opacity-75">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="rounded-xl border bg-card p-3.5 shadow-xs">
          <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider block">
            Total SKUs
          </span>
          <div className="text-lg font-bold text-foreground mt-1">
            {summary ? summary.total_items : "—"}
          </div>
          <span className="text-[10px] text-muted-foreground">Unique listings</span>
        </div>

        <div className="rounded-xl border bg-card p-3.5 shadow-xs">
          <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider block">
            On-Hand Units
          </span>
          <div className="text-lg font-bold text-foreground mt-1">
            {summary ? summary.total_on_hand_units.toLocaleString("en-IN") : "—"}
          </div>
          <span className="text-[10px] text-muted-foreground">Total warehouse stock</span>
        </div>

        <div className="rounded-xl border bg-card p-3.5 shadow-xs">
          <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider block">
            Active Holds
          </span>
          <div className="text-lg font-bold text-blue-600 mt-1">
            {summary ? summary.total_reserved_units.toLocaleString("en-IN") : "—"}
          </div>
          <span className="text-[10px] text-muted-foreground">Reserved by customers</span>
        </div>

        <div className="rounded-xl border bg-card p-3.5 shadow-xs">
          <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider block">
            Available to Sell
          </span>
          <div className="text-lg font-bold text-emerald-600 mt-1">
            {summary ? summary.total_available_units.toLocaleString("en-IN") : "—"}
          </div>
          <span className="text-[10px] text-muted-foreground">Available for checkout</span>
        </div>

        <div className="rounded-xl border bg-card p-3.5 shadow-xs">
          <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider block">
            Low Stock Alerts
          </span>
          <div className="text-lg font-bold text-amber-600 mt-1">
            {summary ? summary.low_stock_count : "—"}
          </div>
          <span className="text-[10px] text-muted-foreground">Below alert threshold</span>
        </div>

        <div className="rounded-xl border bg-card p-3.5 shadow-xs">
          <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider block">
            Out of Stock
          </span>
          <div className="text-lg font-bold text-red-600 mt-1">
            {summary ? summary.out_of_stock_count : "—"}
          </div>
          <span className="text-[10px] text-muted-foreground">0 available units</span>
        </div>
      </div>

      {/* Search & Status Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search inventory by product name, variant, or SKU..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9 text-xs"
          />
        </div>

        <div className="flex items-center gap-1.5 border rounded-lg p-1 bg-card shrink-0">
          <button
            onClick={() => setStatusFilter("ALL")}
            className={`px-3 py-1 text-xs rounded-md font-medium transition-colors ${
              statusFilter === "ALL"
                ? "bg-blue-600 text-white"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            All Items
          </button>
          <button
            onClick={() => setStatusFilter("LOW_STOCK")}
            className={`px-3 py-1 text-xs rounded-md font-medium transition-colors ${
              statusFilter === "LOW_STOCK"
                ? "bg-amber-600 text-white"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            Low Stock ({summary?.low_stock_count ?? 0})
          </button>
          <button
            onClick={() => setStatusFilter("OUT_OF_STOCK")}
            className={`px-3 py-1 text-xs rounded-md font-medium transition-colors ${
              statusFilter === "OUT_OF_STOCK"
                ? "bg-red-600 text-white"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            Out of Stock ({summary?.out_of_stock_count ?? 0})
          </button>
          <button
            onClick={() => setStatusFilter("IN_STOCK")}
            className={`px-3 py-1 text-xs rounded-md font-medium transition-colors ${
              statusFilter === "IN_STOCK"
                ? "bg-emerald-600 text-white"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            In Stock
          </button>
        </div>
      </div>

      {/* Inventory Table */}
      <div className="rounded-xl border bg-card shadow-xs overflow-hidden">
        {isLoading ? (
          <div className="p-12 text-center text-muted-foreground">
            <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-solid border-emerald-600 border-r-transparent align-[-0.125em] mb-2" />
            <p className="text-sm">Loading warehouse stock levels...</p>
          </div>
        ) : !dashboard || dashboard.items.length === 0 ? (
          <div className="p-12 text-center space-y-3">
            <Boxes className="h-8 w-8 mx-auto text-zinc-400" />
            <h3 className="font-semibold text-foreground text-sm">No Inventory Records Found</h3>
            <p className="text-xs text-muted-foreground">
              {searchQuery || statusFilter !== "ALL"
                ? "No inventory matches your active filter criteria."
                : "You have not published any product listings in your store yet."}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-muted/50 border-b text-muted-foreground uppercase text-[10px] tracking-wider">
                <tr>
                  <th className="py-3 px-4 font-semibold">Product & Variant</th>
                  <th className="py-3 px-4 font-semibold">SKU / Store SKU</th>
                  <th className="py-3 px-4 font-semibold text-right">Selling Price</th>
                  <th className="py-3 px-4 font-semibold text-center">On-Hand</th>
                  <th className="py-3 px-4 font-semibold text-center">Reserved Holds</th>
                  <th className="py-3 px-4 font-semibold text-center">Available Stock</th>
                  <th className="py-3 px-4 font-semibold text-center">Alert Threshold</th>
                  <th className="py-3 px-4 font-semibold text-center">Stock Status</th>
                  <th className="py-3 px-4 font-semibold text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {dashboard.items.map((item) => (
                  <tr key={item.listing_id} className="hover:bg-muted/30 transition-colors">
                    <td className="py-3 px-4">
                      <div className="font-semibold text-foreground text-sm line-clamp-1">
                        {item.product_name}
                      </div>
                      <div className="text-[11px] text-muted-foreground">{item.variant_name}</div>
                    </td>

                    <td className="py-3 px-4 font-mono text-[11px]">
                      <div>{item.sku}</div>
                      {item.seller_sku && (
                        <div className="text-[10px] text-muted-foreground">Store: {item.seller_sku}</div>
                      )}
                    </td>

                    <td className="py-3 px-4 text-right font-mono font-medium text-foreground">
                      ₹{(item.selling_price_paise / 100).toFixed(2)}
                    </td>

                    <td className="py-3 px-4 text-center font-mono font-semibold text-foreground">
                      {item.on_hand_quantity}
                    </td>

                    <td className="py-3 px-4 text-center font-mono text-blue-600">
                      {item.reserved_quantity > 0 ? (
                        <span className="font-bold bg-blue-50 dark:bg-blue-950/60 px-1.5 py-0.5 rounded-md">
                          {item.reserved_quantity}
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>

                    <td className="py-3 px-4 text-center font-mono font-bold text-sm">
                      <span
                        className={
                          item.is_out_of_stock
                            ? "text-red-600 dark:text-red-400"
                            : item.is_low_stock
                            ? "text-amber-600 dark:text-amber-400"
                            : "text-emerald-600 dark:text-emerald-400"
                        }
                      >
                        {item.available_quantity}
                      </span>
                    </td>

                    <td className="py-3 px-4 text-center font-mono text-muted-foreground">
                      ≤ {item.low_stock_threshold}
                    </td>

                    <td className="py-3 px-4 text-center">
                      {item.is_out_of_stock ? (
                        <Badge className="bg-red-100 text-red-800 dark:bg-red-950/60 dark:text-red-300 border-0">
                          Out of Stock
                        </Badge>
                      ) : item.is_low_stock ? (
                        <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border-0">
                          Low Stock Alert
                        </Badge>
                      ) : (
                        <Badge className="bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border-0">
                          In Stock
                        </Badge>
                      )}
                    </td>

                    <td className="py-3 px-4 text-right">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => openAdjustModal(item)}
                        className="gap-1.5 text-xs h-7"
                      >
                        <SlidersHorizontal className="h-3.5 w-3.5" />
                        Adjust
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Adjust Inventory Modal */}
      {adjustingItem && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-card border rounded-2xl max-w-md w-full p-6 shadow-xl space-y-4 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between border-b pb-3">
              <div>
                <h3 className="font-bold text-foreground text-base">Adjust Warehouse Stock</h3>
                <p className="text-xs text-muted-foreground line-clamp-1">
                  {adjustingItem.product_name} • {adjustingItem.variant_name}
                </p>
              </div>
              <button onClick={closeAdjustModal} className="text-muted-foreground hover:text-foreground">
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Current Metrics Card */}
            <div className="grid grid-cols-3 gap-2 p-3 rounded-lg bg-muted/40 border text-center text-xs">
              <div>
                <span className="text-[10px] text-muted-foreground uppercase block">Current On-Hand</span>
                <span className="font-bold font-mono text-sm text-foreground">
                  {adjustingItem.on_hand_quantity}
                </span>
              </div>
              <div>
                <span className="text-[10px] text-blue-600 uppercase block">Reserved Holds</span>
                <span className="font-bold font-mono text-sm text-blue-600">
                  {adjustingItem.reserved_quantity}
                </span>
              </div>
              <div>
                <span className="text-[10px] text-emerald-600 uppercase block">Available</span>
                <span className="font-bold font-mono text-sm text-emerald-600">
                  {adjustingItem.available_quantity}
                </span>
              </div>
            </div>

            {modalError && (
              <div className="p-3 rounded-lg border border-red-500/30 bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 text-xs flex items-center gap-2">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{modalError}</span>
              </div>
            )}

            <form onSubmit={handleAdjustSubmit} className="space-y-3.5 text-xs">
              <div>
                <label className="font-medium text-foreground block mb-1.5">Adjustment Mode</label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setAdjustType("SET");
                      setAdjustQuantity(String(adjustingItem.on_hand_quantity));
                    }}
                    className={`py-2 px-3 rounded-lg border text-xs font-semibold text-center transition-all ${
                      adjustType === "SET"
                        ? "bg-blue-600 text-white border-blue-600 shadow-xs"
                        : "bg-card text-muted-foreground hover:text-foreground hover:bg-muted"
                    }`}
                  >
                    Set Exact Count
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setAdjustType("DELTA");
                      setAdjustQuantity("10");
                    }}
                    className={`py-2 px-3 rounded-lg border text-xs font-semibold text-center transition-all ${
                      adjustType === "DELTA"
                        ? "bg-blue-600 text-white border-blue-600 shadow-xs"
                        : "bg-card text-muted-foreground hover:text-foreground hover:bg-muted"
                    }`}
                  >
                    Add / Remove (+ / -)
                  </button>
                </div>
              </div>

              <div>
                <label className="font-medium text-foreground block mb-1">
                  {adjustType === "SET"
                    ? "New On-Hand Stock (Must be ≥ active holds)"
                    : "Quantity to Add or Remove (e.g. +20 or -5)"}
                </label>
                <Input
                  type="number"
                  value={adjustQuantity}
                  onChange={(e) => setAdjustQuantity(e.target.value)}
                  required
                  className="font-mono text-sm font-semibold"
                />
              </div>

              <div>
                <label className="font-medium text-foreground block mb-1">
                  Low Stock Alert Threshold
                </label>
                <Input
                  type="number"
                  min="0"
                  value={adjustThreshold}
                  onChange={(e) => setAdjustThreshold(e.target.value)}
                  className="font-mono text-xs"
                />
                <span className="text-[10px] text-muted-foreground">
                  Triggers dashboard alerts when available stock drops to or below this count.
                </span>
              </div>

              <div>
                <label className="font-medium text-foreground block mb-1">
                  Adjustment Reason (Optional)
                </label>
                <Input
                  type="text"
                  placeholder="e.g. Inbound purchase shipment PO-428"
                  value={adjustReason}
                  onChange={(e) => setAdjustReason(e.target.value)}
                  maxLength={255}
                  className="text-xs"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t">
                <Button type="button" variant="outline" size="sm" onClick={closeAdjustModal}>
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={isSubmittingAdjust}
                  className="bg-emerald-600 hover:bg-emerald-700 text-white"
                >
                  {isSubmittingAdjust ? "Updating Stock..." : "Confirm Stock Adjustment"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
