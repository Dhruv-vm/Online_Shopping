"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth/auth-context";
import { apiClient, ApiClientError } from "@/lib/api/client";
import { ProtectedRoute } from "@/components/auth/protected-route";
import { AccountNav } from "@/components/account/account-nav";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { formatPrice } from "@/lib/utils";
import type { OrderListItem } from "@/types";
import {
  User as UserIcon,
  Mail,
  Phone,
  Shield,
  Calendar,
  MapPin,
  Lock,
  LogOut,
  AlertCircle,
  CheckCircle2,
  Loader2,
  Package,
  ArrowRight,
  Clock,
  Truck,
} from "lucide-react";

export default function AccountOverviewPage() {
  const router = useRouter();
  const { user, logout } = useAuth();
  const [isLoggingOutAll, setIsLoggingOutAll] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [recentOrders, setRecentOrders] = useState<OrderListItem[]>([]);
  const [ordersLoading, setOrdersLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    apiClient
      .listOrders(3, 0)
      .then((res) => {
        if (isMounted) {
          setRecentOrders(res.items || res.orders || []);
        }
      })
      .catch(() => {
        // Silently handle if unauthenticated or error
      })
      .finally(() => {
        if (isMounted) setOrdersLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const formattedDate = user?.created_at
    ? new Date(user.created_at).toLocaleDateString("en-IN", {
        year: "numeric",
        month: "long",
        day: "numeric",
      })
    : "Recently joined";

  const handleLogoutAll = async () => {
    if (!window.confirm("Are you sure you want to log out of all active devices?")) {
      return;
    }

    setIsLoggingOutAll(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      await apiClient.logoutAll();
      setSuccessMessage("All sessions terminated. Redirecting to home...");
      setTimeout(async () => {
        await logout();
        router.push("/");
      }, 1000);
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setErrorMessage(err.message || "Failed to log out of all sessions.");
      } else {
        setErrorMessage("Network error: Unable to terminate sessions.");
      }
      setIsLoggingOutAll(false);
    }
  };

  return (
    <ProtectedRoute>
      <div className="container mx-auto px-4 py-8 sm:py-12 max-w-6xl">
        <div className="flex flex-col md:flex-row gap-8 items-start">
          <AccountNav />

          <main className="flex-1 w-full space-y-6">
            {/* Header Greeting */}
            <div className="rounded-2xl border bg-gradient-to-r from-emerald-700 to-teal-800 p-6 sm:p-8 text-white shadow-sm">
              <Badge variant="outline" className="text-white border-white/30 mb-3 bg-white/10 font-medium">
                Customer Account
              </Badge>
              <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">
                Hello, {user?.full_name || "Valued Customer"}!
              </h1>
              <p className="mt-2 text-emerald-100 text-sm max-w-xl">
                Manage your profile details, default shipping destinations, and account security preferences.
              </p>
            </div>

            {successMessage && (
              <div
                role="alert"
                className="flex items-center gap-3 rounded-xl border border-emerald-500/20 bg-emerald-500/10 p-4 text-sm text-emerald-700 dark:text-emerald-400"
              >
                <CheckCircle2 className="h-5 w-5 shrink-0" />
                <span className="font-medium">{successMessage}</span>
              </div>
            )}

            {errorMessage && (
              <div
                role="alert"
                className="flex items-center gap-3 rounded-xl border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-700 dark:text-red-400"
              >
                <AlertCircle className="h-5 w-5 shrink-0" />
                <span className="font-medium">{errorMessage}</span>
              </div>
            )}

            {/* Profile Information */}
            <Card>
              <CardHeader className="pb-4">
                <CardTitle className="text-lg font-semibold flex items-center gap-2">
                  <UserIcon className="h-5 w-5 text-emerald-600" />
                  Personal Information
                </CardTitle>
                <CardDescription>
                  Your verified customer profile as registered on BASKET
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="p-3.5 rounded-lg border bg-muted/20 space-y-1">
                    <span className="text-xs text-muted-foreground flex items-center gap-1.5 font-medium">
                      <UserIcon className="h-3.5 w-3.5" /> Full Name
                    </span>
                    <p className="text-sm font-semibold text-foreground">
                      {user?.full_name || "—"}
                    </p>
                  </div>

                  <div className="p-3.5 rounded-lg border bg-muted/20 space-y-1">
                    <span className="text-xs text-muted-foreground flex items-center gap-1.5 font-medium">
                      <Mail className="h-3.5 w-3.5" /> Email Address
                    </span>
                    <p className="text-sm font-semibold text-foreground truncate">
                      {user?.email || "—"}
                    </p>
                  </div>

                  <div className="p-3.5 rounded-lg border bg-muted/20 space-y-1">
                    <span className="text-xs text-muted-foreground flex items-center gap-1.5 font-medium">
                      <Phone className="h-3.5 w-3.5" /> Mobile Phone
                    </span>
                    <p className="text-sm font-semibold text-foreground">
                      {user?.phone || "Not provided"}
                    </p>
                  </div>

                  <div className="p-3.5 rounded-lg border bg-muted/20 space-y-1">
                    <span className="text-xs text-muted-foreground flex items-center gap-1.5 font-medium">
                      <Calendar className="h-3.5 w-3.5" /> Member Since
                    </span>
                    <p className="text-sm font-semibold text-foreground">
                      {formattedDate}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Quick Actions Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <Link href="/orders" className="block group">
                <Card className="h-full hover:border-emerald-600/50 hover:shadow-md transition-all cursor-pointer">
                  <CardContent className="p-5 flex items-start gap-3.5">
                    <div className="p-2.5 rounded-xl bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 group-hover:scale-105 transition-transform">
                      <Package className="h-5 w-5" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-foreground group-hover:text-emerald-600 transition-colors text-sm">
                        My Orders
                      </h3>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        Track deliveries, view receipts, and initiate returns
                      </p>
                    </div>
                  </CardContent>
                </Card>
              </Link>

              <Link href="/account/addresses" className="block group">
                <Card className="h-full hover:border-emerald-600/50 hover:shadow-md transition-all cursor-pointer">
                  <CardContent className="p-5 flex items-start gap-3.5">
                    <div className="p-2.5 rounded-xl bg-teal-50 text-teal-700 dark:bg-teal-950/60 dark:text-teal-300 group-hover:scale-105 transition-transform">
                      <MapPin className="h-5 w-5" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-foreground group-hover:text-emerald-600 transition-colors text-sm">
                        Saved Addresses
                      </h3>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        Manage delivery destinations and default address
                      </p>
                    </div>
                  </CardContent>
                </Card>
              </Link>

              <Card className="h-full">
                <CardContent className="p-5 flex items-start gap-3.5">
                  <div className="p-2.5 rounded-xl bg-muted text-muted-foreground">
                    <Shield className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-foreground text-sm">Security & Sessions</h3>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Argon2id hashing & HttpOnly cookie protection
                    </p>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Recent Orders Overview */}
            <Card>
              <CardHeader className="pb-3 flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-base font-semibold flex items-center gap-2">
                    <Package className="h-4 w-4 text-emerald-600" />
                    Recent Purchases
                  </CardTitle>
                  <CardDescription className="text-xs">
                    Your latest orders and live shipment status
                  </CardDescription>
                </div>
                <Link href="/orders">
                  <Button variant="ghost" size="sm" className="text-xs text-emerald-600 hover:text-emerald-700 gap-1">
                    View All Orders
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Button>
                </Link>
              </CardHeader>
              <CardContent className="pt-0">
                {ordersLoading ? (
                  <div className="flex items-center justify-center py-6 text-muted-foreground text-xs gap-2">
                    <Loader2 className="h-4 w-4 animate-spin text-emerald-600" />
                    Loading recent orders...
                  </div>
                ) : recentOrders.length === 0 ? (
                  <div className="text-center py-6 border border-dashed rounded-lg space-y-2">
                    <Package className="h-8 w-8 text-muted-foreground mx-auto stroke-1" />
                    <p className="text-xs text-muted-foreground">No orders placed yet.</p>
                    <Link href="/products">
                      <Button size="sm" variant="outline" className="text-xs">
                        Start Shopping
                      </Button>
                    </Link>
                  </div>
                ) : (
                  <div className="divide-y divide-muted/60">
                    {recentOrders.map((ord) => (
                      <div key={ord.id} className="py-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 text-xs">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="font-mono font-semibold text-foreground">{ord.order_number}</span>
                            <Badge variant={ord.status === "CONFIRMED" || ord.status === "DELIVERED" ? "default" : "secondary"} className="text-[10px]">
                              {ord.status}
                            </Badge>
                          </div>
                          <div className="flex items-center gap-2 text-muted-foreground text-[11px]">
                            <span>
                              {new Date(ord.created_at).toLocaleDateString("en-IN", {
                                year: "numeric",
                                month: "short",
                                day: "numeric",
                              })}
                            </span>
                            <span>•</span>
                            <span>{ord.item_count ?? 1} {(ord.item_count ?? 1) === 1 ? "item" : "items"}</span>
                            <span>•</span>
                            <span className="font-semibold text-foreground">{formatPrice(ord.total_payable_paise)}</span>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <Link href={`/orders/${ord.id}`}>
                            <Button size="sm" variant="outline" className="h-7 text-xs">
                              Details
                            </Button>
                          </Link>
                          <Link href={`/orders/${ord.id}/track`}>
                            <Button size="sm" className="h-7 text-xs bg-emerald-600 hover:bg-emerald-700 text-white gap-1">
                              <Truck className="h-3 w-3" />
                              Track
                            </Button>
                          </Link>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Security Actions */}
            <Card className="border-red-200/50 dark:border-red-950/50">
              <CardHeader className="pb-3">
                <CardTitle className="text-base font-semibold flex items-center gap-2 text-foreground">
                  <Lock className="h-4 w-4 text-muted-foreground" />
                  Session & Device Management
                </CardTitle>
                <CardDescription>
                  Revoke access from all active browser sessions across all devices
                </CardDescription>
              </CardHeader>
              <CardContent className="pt-2">
                <Button
                  variant="outline"
                  onClick={handleLogoutAll}
                  disabled={isLoggingOutAll}
                  className="border-red-300 text-red-600 hover:bg-red-50 hover:text-red-700 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-950/40 text-xs sm:text-sm font-medium"
                >
                  {isLoggingOutAll ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Terminating All Sessions...
                    </>
                  ) : (
                    <>
                      <LogOut className="mr-2 h-4 w-4" />
                      Sign Out From All Devices
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>
          </main>
        </div>
      </div>
    </ProtectedRoute>
  );
}
