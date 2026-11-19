"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import {
  Store,
  LayoutDashboard,
  Settings,
  Package,
  Layers,
  AlertTriangle,
  ArrowLeft,
  ChevronRight,
  ExternalLink,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth/auth-context";
import { apiClient } from "@/lib/api/client";
import type { RetailerProfile } from "@/types";

export default function RetailerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, isAuthenticated, isLoading } = useAuth();
  const [profile, setProfile] = useState<RetailerProfile | null>(null);

  useEffect(() => {
    let mounted = true;
    if (isAuthenticated && user?.role === "retailer") {
      apiClient
        .getRetailerProfile()
        .then((res) => {
          if (mounted) setProfile(res);
        })
        .catch(() => {
          // Handled gracefully
        });
    }
    return () => {
      mounted = false;
    };
  }, [isAuthenticated, user?.role]);

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-16 text-center">
        <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-blue-600 border-r-transparent align-[-0.125em]" />
        <p className="mt-4 text-sm text-muted-foreground">Authenticating merchant portal access...</p>
      </div>
    );
  }

  // Not authenticated -> redirect to login
  if (!isAuthenticated) {
    router.push("/login?redirect=/retailer");
    return null;
  }

  // Authenticated but not a retailer -> 403 Forbidden screen
  if (user?.role !== "retailer") {
    return (
      <div className="container mx-auto px-4 py-16 max-w-xl text-center">
        <div className="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-amber-100 text-amber-700 dark:bg-amber-950/50 mb-6">
          <Store className="h-8 w-8" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground mb-2">
          Merchant Portal Access Required
        </h1>
        <p className="text-sm text-muted-foreground mb-6">
          You are currently signed in as <strong className="text-foreground">{user?.email}</strong> with role{" "}
          <Badge variant="outline" className="capitalize text-xs">{user?.role || "customer"}</Badge>.
          The Retailer Portal is reserved for registered business sellers on BASKET.
        </p>
        <div className="flex flex-col sm:flex-row justify-center gap-3">
          <Link href="/register/retailer">
            <Button className="bg-blue-600 hover:bg-blue-700 text-white w-full sm:w-auto">
              Register as a Partner Retailer
            </Button>
          </Link>
          <Link href="/">
            <Button variant="outline" className="gap-2 w-full sm:w-auto">
              <ArrowLeft className="h-4 w-4" />
              Return to Storefront
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  const isPendingVerification = profile?.verification_status === "PENDING";
  const isSuspended = profile?.verification_status === "SUSPENDED";

  return (
    <div className="min-h-screen bg-muted/20">
      {/* Top Banner */}
      <div className="bg-blue-950 text-blue-100 border-b border-blue-900/60 px-4 py-2 text-xs flex items-center justify-between">
        <div className="container mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Store className="h-4 w-4 text-blue-400" />
            <span className="font-semibold tracking-wide">
              {profile?.name ? profile.name.toUpperCase() : "MERCHANT PORTAL"}
            </span>
            <Badge className="bg-blue-800 text-[10px] px-1.5 py-0 text-blue-200 border-0">
              Retailer Center
            </Badge>
          </div>
          <div className="flex items-center gap-4 text-blue-300">
            <span>Store Status: <strong className={profile?.is_open ? "text-emerald-400" : "text-amber-400"}>
              {profile?.is_open ? "● Live / Open" : "○ Closed"}
            </strong></span>
            {profile?.slug && (
              <Link
                href={`/retailers/${profile.slug}`}
                className="hover:text-white flex items-center gap-1 underline text-[11px]"
              >
                View Public Store <ExternalLink className="h-3 w-3" />
              </Link>
            )}
          </div>
        </div>
      </div>

      {/* Verification Warning Alert Banner if Pending or Suspended */}
      {isPendingVerification && (
        <div className="bg-amber-500/15 border-b border-amber-500/30 text-amber-900 dark:text-amber-200 px-4 py-3 text-xs">
          <div className="container mx-auto flex items-center gap-2.5">
            <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0" />
            <div>
              <strong>Merchant Verification In Review:</strong> Your store onboarding is currently pending verification by BASKET platform administrators. Your store profile and inventory are staged and will be activated for marketplace checkout upon verification.
            </div>
          </div>
        </div>
      )}
      {isSuspended && (
        <div className="bg-red-500/15 border-b border-red-500/30 text-red-900 dark:text-red-200 px-4 py-3 text-xs">
          <div className="container mx-auto flex items-center gap-2.5">
            <AlertTriangle className="h-4 w-4 text-red-600 shrink-0" />
            <div>
              <strong>Store Suspended:</strong> This retailer account has been suspended by platform operations. Contact support to resolve compliance questions.
            </div>
          </div>
        </div>
      )}

      <div className="container mx-auto px-4 sm:px-6 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          {/* Retailer Sidebar Navigation */}
          <aside className="lg:col-span-1 space-y-2">
            <div className="rounded-xl border bg-card p-4 shadow-xs">
              <div className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-3 px-2">
                Merchant Desk
              </div>
              <nav className="space-y-1 text-sm font-medium">
                <Link
                  href="/retailer"
                  className={`flex items-center justify-between px-3 py-2 rounded-lg transition-colors ${
                    pathname === "/retailer"
                      ? "bg-blue-50 text-blue-700 dark:bg-blue-950/50 dark:text-blue-300 font-semibold"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <LayoutDashboard className="h-4 w-4" />
                    Dashboard
                  </div>
                  {pathname === "/retailer" && <ChevronRight className="h-4 w-4 text-blue-400" />}
                </Link>

                <Link
                  href="/retailer/profile"
                  className={`flex items-center justify-between px-3 py-2 rounded-lg transition-colors ${
                    pathname === "/retailer/profile"
                      ? "bg-blue-50 text-blue-700 dark:bg-blue-950/50 dark:text-blue-300 font-semibold"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <Settings className="h-4 w-4" />
                    Store Settings
                  </div>
                  {pathname === "/retailer/profile" && <ChevronRight className="h-4 w-4 text-blue-400" />}
                </Link>

                <div className="pt-2 pb-1 text-xs font-bold text-muted-foreground uppercase tracking-wider px-2">
                  Catalogue & Inventory
                </div>

                <Link
                  href="/products"
                  className="flex items-center gap-2.5 px-3 py-2 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                >
                  <Layers className="h-4 w-4" />
                  Product Catalogue
                </Link>

                <Link
                  href="/orders"
                  className="flex items-center gap-2.5 px-3 py-2 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                >
                  <Package className="h-4 w-4" />
                  Orders & Returns
                </Link>
              </nav>
            </div>
          </aside>

          {/* Retailer Main Viewport */}
          <main className="lg:col-span-4">{children}</main>
        </div>
      </div>
    </div>
  );
}
