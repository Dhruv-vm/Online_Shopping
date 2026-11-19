"use client";

import { useEffect, useState } from "react";
import {
  Users,
  Store,
  ShoppingBag,
  TrendingUp,
  AlertCircle,
  CheckCircle2,
  XCircle,
  RefreshCw,
  Search,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiClient } from "@/lib/api/client";
import type { AdminOverview, AdminRetailerListItem } from "@/types";

export default function AdminOverviewPage() {
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [retailers, setRetailers] = useState<AdminRetailerListItem[]>([]);
  const [filterStatus, setFilterStatus] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const loadData = async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const [overviewData, retailersData] = await Promise.all([
        apiClient.getAdminOverview(),
        apiClient.listAdminRetailers(),
      ]);
      setOverview(overviewData);
      setRetailers(retailersData);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to load admin metrics.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleVerify = async (retailerId: string, status: "VERIFIED" | "SUSPENDED") => {
    setActionLoading(retailerId);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      const updated = await apiClient.verifyRetailer(retailerId, status);
      setRetailers((prev) =>
        prev.map((r) => (r.id === retailerId ? updated : r))
      );
      setSuccessMsg(
        `Retailer "${updated.name}" has been marked as ${status}.`
      );
      // Reload overview KPI counter
      const newOverview = await apiClient.getAdminOverview();
      setOverview(newOverview);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to update retailer status.");
    } finally {
      setActionLoading(null);
    }
  };

  const filteredRetailers = retailers.filter((r) => {
    const matchesStatus =
      filterStatus === "ALL" || r.verification_status === filterStatus;
    const matchesSearch =
      !searchQuery ||
      r.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (r.owner_email && r.owner_email.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (r.state && r.state.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchesStatus && matchesSearch;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Marketplace Command Dashboard
          </h1>
          <p className="text-sm text-muted-foreground">
            Platform governance, cross-retailer KPIs, and merchant onboarding verification.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={loadData}
          disabled={isLoading}
          className="gap-2 shrink-0"
        >
          <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
          Refresh Metrics
        </Button>
      </div>

      {/* Alerts */}
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

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <div className="rounded-xl border bg-card p-4 shadow-xs">
          <div className="flex items-center justify-between text-muted-foreground mb-2">
            <span className="text-xs font-semibold">Total Revenue</span>
            <TrendingUp className="h-4 w-4 text-purple-600" />
          </div>
          <div className="text-xl font-bold text-foreground">
            {overview
              ? `₹${(overview.total_revenue_paise / 100).toLocaleString("en-IN")}`
              : "—"}
          </div>
          <span className="text-[11px] text-muted-foreground">Settled payments</span>
        </div>

        <div className="rounded-xl border bg-card p-4 shadow-xs">
          <div className="flex items-center justify-between text-muted-foreground mb-2">
            <span className="text-xs font-semibold">Total Orders</span>
            <ShoppingBag className="h-4 w-4 text-emerald-600" />
          </div>
          <div className="text-xl font-bold text-foreground">
            {overview ? overview.total_orders.toLocaleString("en-IN") : "—"}
          </div>
          <span className="text-[11px] text-muted-foreground">Platform-wide</span>
        </div>

        <div className="rounded-xl border bg-card p-4 shadow-xs">
          <div className="flex items-center justify-between text-muted-foreground mb-2">
            <span className="text-xs font-semibold">Customers</span>
            <Users className="h-4 w-4 text-blue-600" />
          </div>
          <div className="text-xl font-bold text-foreground">
            {overview ? overview.total_customers.toLocaleString("en-IN") : "—"}
          </div>
          <span className="text-[11px] text-muted-foreground">Registered users</span>
        </div>

        <div className="rounded-xl border bg-card p-4 shadow-xs">
          <div className="flex items-center justify-between text-muted-foreground mb-2">
            <span className="text-xs font-semibold">Retailers</span>
            <Store className="h-4 w-4 text-amber-600" />
          </div>
          <div className="text-xl font-bold text-foreground">
            {overview ? overview.total_retailers.toLocaleString("en-IN") : "—"}
          </div>
          <span className="text-[11px] text-muted-foreground">Active & pending</span>
        </div>

        <div className="rounded-xl border bg-card p-4 shadow-xs">
          <div className="flex items-center justify-between text-muted-foreground mb-2">
            <span className="text-xs font-semibold">Pending Verification</span>
            <AlertCircle className="h-4 w-4 text-red-500" />
          </div>
          <div className="text-xl font-bold text-foreground">
            {overview ? overview.pending_verifications : "—"}
          </div>
          <span className="text-[11px] text-red-500 font-medium">Requires approval</span>
        </div>

        <div className="rounded-xl border bg-card p-4 shadow-xs">
          <div className="flex items-center justify-between text-muted-foreground mb-2">
            <span className="text-xs font-semibold">Catalogue Items</span>
            <Store className="h-4 w-4 text-indigo-600" />
          </div>
          <div className="text-xl font-bold text-foreground">
            {overview ? overview.active_products : "—"}
          </div>
          <span className="text-[11px] text-muted-foreground">Verified products</span>
        </div>
      </div>

      {/* Retailer Management Queue Section */}
      <div className="rounded-xl border bg-card shadow-xs overflow-hidden">
        <div className="p-4 border-b bg-muted/20 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-base font-bold text-foreground">
              Retailer Onboarding & Verification Desk
            </h2>
            <p className="text-xs text-muted-foreground">
              Review seller business profiles, approve marketplace selling rights, or suspend accounts.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                type="text"
                placeholder="Search store, owner, state..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-8 h-8 text-xs w-48 sm:w-60"
              />
            </div>
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="h-8 rounded-md border border-input bg-background px-2 text-xs"
            >
              <option value="ALL">All Statuses</option>
              <option value="PENDING">Pending Verification</option>
              <option value="VERIFIED">Verified</option>
              <option value="SUSPENDED">Suspended</option>
            </select>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b bg-muted/40 text-muted-foreground font-semibold">
              <tr>
                <th className="py-3 px-4">Store / Business Name</th>
                <th className="py-3 px-4">State</th>
                <th className="py-3 px-4">Owner Contact</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Store Open</th>
                <th className="py-3 px-4 text-right">Moderation Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-muted-foreground">
                    Loading retailer registry...
                  </td>
                </tr>
              ) : filteredRetailers.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-muted-foreground">
                    No retailers found matching the selected filter.
                  </td>
                </tr>
              ) : (
                filteredRetailers.map((r) => (
                  <tr key={r.id} className="hover:bg-muted/10 transition-colors">
                    <td className="py-3 px-4">
                      <div className="font-semibold text-foreground">{r.name}</div>
                      <div className="text-[11px] text-muted-foreground font-mono">
                        slug: {r.slug}
                      </div>
                      {r.business_address && (
                        <div className="text-[11px] text-muted-foreground truncate max-w-xs">
                          {r.business_address}
                        </div>
                      )}
                    </td>
                    <td className="py-3 px-4 font-mono">{r.state || "—"}</td>
                    <td className="py-3 px-4">
                      <div>{r.owner_name || "—"}</div>
                      <div className="text-[11px] text-muted-foreground">
                        {r.owner_email || r.contact_email || "—"}
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      {r.verification_status === "VERIFIED" && (
                        <Badge className="bg-emerald-100 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300 border-0">
                          Verified
                        </Badge>
                      )}
                      {r.verification_status === "PENDING" && (
                        <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-950/50 dark:text-amber-300 border-0">
                          Pending Review
                        </Badge>
                      )}
                      {r.verification_status === "SUSPENDED" && (
                        <Badge className="bg-red-100 text-red-800 dark:bg-red-950/50 dark:text-red-300 border-0">
                          Suspended
                        </Badge>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`inline-block h-2 w-2 rounded-full mr-1.5 ${
                          r.is_open ? "bg-emerald-500" : "bg-zinc-400"
                        }`}
                      />
                      {r.is_open ? "Open" : "Closed"}
                    </td>
                    <td className="py-3 px-4 text-right space-x-2">
                      {r.verification_status !== "VERIFIED" && (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={actionLoading === r.id}
                          onClick={() => handleVerify(r.id, "VERIFIED")}
                          className="h-7 text-xs border-emerald-600/40 text-emerald-700 hover:bg-emerald-50 dark:text-emerald-300"
                        >
                          <CheckCircle2 className="h-3 w-3 mr-1" />
                          Approve
                        </Button>
                      )}
                      {r.verification_status !== "SUSPENDED" && (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={actionLoading === r.id}
                          onClick={() => handleVerify(r.id, "SUSPENDED")}
                          className="h-7 text-xs border-red-600/40 text-red-600 hover:bg-red-50 dark:text-red-400"
                        >
                          <XCircle className="h-3 w-3 mr-1" />
                          Suspend
                        </Button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
