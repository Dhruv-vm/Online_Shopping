"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Store,
  Layers,
  Boxes,
  PlusCircle,
  Star,
  Power,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Settings,
  MapPin,
  Phone,
  Mail,
  AlertTriangle,
  ArrowRight,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api/client";
import type { RetailerOverview, RetailerProfile } from "@/types";

export default function RetailerDashboardPage() {
  const [overview, setOverview] = useState<RetailerOverview | null>(null);
  const [profile, setProfile] = useState<RetailerProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [togglingOpen, setTogglingOpen] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const loadData = async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const [overviewData, profileData] = await Promise.all([
        apiClient.getRetailerOverview(),
        apiClient.getRetailerProfile(),
      ]);
      setOverview(overviewData);
      setProfile(profileData);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to load store metrics.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleToggleStoreOpen = async () => {
    if (!profile) return;
    setTogglingOpen(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      const nextOpenState = !profile.is_open;
      const updated = await apiClient.updateRetailerProfile({
        is_open: nextOpenState,
      });
      setProfile(updated);
      setOverview((prev) => (prev ? { ...prev, is_open: nextOpenState } : null));
      setSuccessMsg(
        nextOpenState
          ? "Store is now LIVE and open for customer orders."
          : "Store is now CLOSED. Inventory will be displayed as paused."
      );
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to toggle store status.");
    } finally {
      setTogglingOpen(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              {profile?.name || "Merchant Store Dashboard"}
            </h1>
            {profile?.verification_status === "VERIFIED" && (
              <Badge className="bg-emerald-100 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300 border-0">
                Verified Merchant
              </Badge>
            )}
            {profile?.verification_status === "PENDING" && (
              <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-950/50 dark:text-amber-300 border-0">
                Pending Verification
              </Badge>
            )}
          </div>
          <p className="text-sm text-muted-foreground">
            Monitor real-time inventory velocity, store status, and marketplace performance.
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <Button
            variant="outline"
            size="sm"
            onClick={loadData}
            disabled={isLoading}
            className="gap-2"
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </Button>

          <Button
            size="sm"
            onClick={handleToggleStoreOpen}
            disabled={togglingOpen || !profile}
            className={`gap-2 text-white font-medium shadow-xs ${
              profile?.is_open
                ? "bg-amber-600 hover:bg-amber-700"
                : "bg-emerald-600 hover:bg-emerald-700"
            }`}
          >
            <Power className="h-4 w-4" />
            {profile?.is_open ? "Pause Store (Close)" : "Open Store (Go Live)"}
          </Button>
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
        <div className="p-3.5 rounded-lg border border-emerald-500/30 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 text-sm flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {/* Low Stock Warning Alert */}
      {overview && (overview.low_stock_alerts > 0 || overview.out_of_stock_alerts > 0) && (
        <div className="p-4 rounded-xl border border-amber-500/30 bg-amber-50/50 dark:bg-amber-950/30 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0" />
            <div className="text-sm">
              <span className="font-semibold text-amber-900 dark:text-amber-200">
                Inventory Alerts Detected:
              </span>{" "}
              <span className="text-amber-800 dark:text-amber-300">
                You have {overview.low_stock_alerts} low-stock listing{overview.low_stock_alerts !== 1 ? "s" : ""}
                {overview.out_of_stock_alerts > 0 ? ` and ${overview.out_of_stock_alerts} out-of-stock item(s)` : ""}.
              </span>
            </div>
          </div>
          <Link href="/retailer/inventory?filter=LOW_STOCK">
            <Button size="sm" variant="outline" className="text-xs gap-1.5 border-amber-500/40 text-amber-900 dark:text-amber-200 hover:bg-amber-100 dark:hover:bg-amber-900/40">
              Review Stock <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </Link>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="rounded-xl border bg-card p-4 shadow-xs">
          <div className="flex items-center justify-between text-muted-foreground mb-2">
            <span className="text-xs font-semibold">Store Status</span>
            <Power className={`h-4 w-4 ${profile?.is_open ? "text-emerald-600" : "text-zinc-400"}`} />
          </div>
          <div className="text-xl font-bold text-foreground">
            {profile?.is_open ? (
              <span className="text-emerald-600 flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-500 animate-pulse" />
                Live / Open
              </span>
            ) : (
              <span className="text-zinc-500 flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full bg-zinc-400" />
                Closed
              </span>
            )}
          </div>
          <span className="text-[11px] text-muted-foreground">Marketplace visibility</span>
        </div>

        <div className="rounded-xl border bg-card p-4 shadow-xs">
          <div className="flex items-center justify-between text-muted-foreground mb-2">
            <span className="text-xs font-semibold">Active Listings</span>
            <Layers className="h-4 w-4 text-blue-600" />
          </div>
          <div className="text-xl font-bold text-foreground">
            {overview ? `${overview.active_listings} / ${overview.total_listings}` : "—"}
          </div>
          <span className="text-[11px] text-muted-foreground">Published catalogue</span>
        </div>

        <div className="rounded-xl border bg-card p-4 shadow-xs">
          <div className="flex items-center justify-between text-muted-foreground mb-2">
            <span className="text-xs font-semibold">Stock on Hand</span>
            <Boxes className="h-4 w-4 text-emerald-600" />
          </div>
          <div className="text-xl font-bold text-foreground">
            {overview ? overview.total_inventory_units.toLocaleString("en-IN") : "—"}
          </div>
          <span className="text-[11px] text-muted-foreground">Units across all SKUs</span>
        </div>

        <div className="rounded-xl border bg-card p-4 shadow-xs">
          <div className="flex items-center justify-between text-muted-foreground mb-2">
            <span className="text-xs font-semibold">Seller Rating</span>
            <Star className="h-4 w-4 text-amber-500 fill-amber-500" />
          </div>
          <div className="text-xl font-bold text-foreground">
            {profile ? `${profile.rating.toFixed(1)} / 5.0` : "5.0"}
          </div>
          <span className="text-[11px] text-muted-foreground">Customer reviews</span>
        </div>
      </div>

      {/* Quick Action Navigation Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Link
          href="/retailer/listings"
          className="rounded-xl border bg-card p-5 shadow-xs hover:border-blue-500/50 hover:shadow-md transition-all group"
        >
          <div className="flex items-center justify-between mb-3">
            <div className="h-10 w-10 rounded-lg bg-blue-100 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300 flex items-center justify-center">
              <Layers className="h-5 w-5" />
            </div>
            <ArrowRight className="h-4 w-4 text-muted-foreground group-hover:text-blue-600 group-hover:translate-x-0.5 transition-all" />
          </div>
          <h3 className="font-semibold text-foreground text-sm">Product Listings</h3>
          <p className="text-xs text-muted-foreground mt-1">
            View, price, and publish product variants in your store catalogue.
          </p>
        </Link>

        <Link
          href="/retailer/listings/new"
          className="rounded-xl border bg-card p-5 shadow-xs hover:border-emerald-500/50 hover:shadow-md transition-all group"
        >
          <div className="flex items-center justify-between mb-3">
            <div className="h-10 w-10 rounded-lg bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 flex items-center justify-center">
              <PlusCircle className="h-5 w-5" />
            </div>
            <ArrowRight className="h-4 w-4 text-muted-foreground group-hover:text-emerald-600 group-hover:translate-x-0.5 transition-all" />
          </div>
          <h3 className="font-semibold text-foreground text-sm">Add Product to Store</h3>
          <p className="text-xs text-muted-foreground mt-1">
            Browse platform catalogue products and list them with custom pricing.
          </p>
        </Link>

        <Link
          href="/retailer/inventory"
          className="rounded-xl border bg-card p-5 shadow-xs hover:border-amber-500/50 hover:shadow-md transition-all group"
        >
          <div className="flex items-center justify-between mb-3">
            <div className="h-10 w-10 rounded-lg bg-amber-100 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 flex items-center justify-center">
              <Boxes className="h-5 w-5" />
            </div>
            <ArrowRight className="h-4 w-4 text-muted-foreground group-hover:text-amber-600 group-hover:translate-x-0.5 transition-all" />
          </div>
          <h3 className="font-semibold text-foreground text-sm">Stock & Inventory</h3>
          <p className="text-xs text-muted-foreground mt-1">
            Adjust on-hand inventory levels and configure low-stock alert thresholds.
          </p>
        </Link>
      </div>

      {/* Store Profile & Contact Summary Card */}
      <div className="rounded-xl border bg-card p-6 shadow-xs space-y-4">
        <div className="flex items-center justify-between border-b pb-3">
          <div>
            <h2 className="text-base font-bold text-foreground">
              Store Profile & Merchant Details
            </h2>
            <p className="text-xs text-muted-foreground">
              Public store details visible to customers on product listings.
            </p>
          </div>
          <Link href="/retailer/profile">
            <Button variant="outline" size="sm" className="gap-2 text-xs">
              <Settings className="h-3.5 w-3.5" />
              Edit Profile
            </Button>
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div className="space-y-2">
            <div>
              <span className="font-semibold text-muted-foreground">Store Name:</span>
              <p className="text-sm font-medium text-foreground">{profile?.name || "—"}</p>
            </div>
            <div>
              <span className="font-semibold text-muted-foreground">Description:</span>
              <p className="text-foreground">{profile?.description || "No description provided."}</p>
            </div>
            <div>
              <span className="font-semibold text-muted-foreground">Operating State:</span>
              <p className="font-mono text-foreground">{profile?.state || "—"}</p>
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-start gap-2">
              <MapPin className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold text-muted-foreground">Business Address:</span>
                <p className="text-foreground">{profile?.business_address || "Not specified."}</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Phone className="h-4 w-4 text-muted-foreground shrink-0" />
              <div>
                <span className="font-semibold text-muted-foreground">Phone:</span>{" "}
                <span className="font-mono text-foreground">{profile?.contact_phone || "—"}</span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Mail className="h-4 w-4 text-muted-foreground shrink-0" />
              <div>
                <span className="font-semibold text-muted-foreground">Email:</span>{" "}
                <span className="font-mono text-foreground">{profile?.contact_email || "—"}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
