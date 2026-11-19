"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Store,
  Layers,
  Boxes,
  ShoppingBag,
  Star,
  Power,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Settings,
  MapPin,
  Phone,
  Mail,
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
            {overview ? overview.total_listings : "—"}
          </div>
          <span className="text-[11px] text-muted-foreground">Catalogue items</span>
        </div>

        <div className="rounded-xl border bg-card p-4 shadow-xs">
          <div className="flex items-center justify-between text-muted-foreground mb-2">
            <span className="text-xs font-semibold">Stock on Hand</span>
            <Boxes className="h-4 w-4 text-emerald-600" />
          </div>
          <div className="text-xl font-bold text-foreground">
            {overview ? overview.total_inventory_units.toLocaleString("en-IN") : "—"}
          </div>
          <span className="text-[11px] text-muted-foreground">Units in inventory</span>
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
