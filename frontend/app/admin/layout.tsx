"use client";

import React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ShieldAlert,
  BarChart3,
  Users,
  Store,
  LayoutGrid,
  ShoppingBag,
  Sliders,
  ChevronRight,
  ArrowLeft,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth/auth-context";

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const { user, isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-16 text-center">
        <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-purple-600 border-r-transparent align-[-0.125em]" />
        <p className="mt-4 text-sm text-muted-foreground">Authenticating administrator access...</p>
      </div>
    );
  }

  // Not authenticated -> redirect to login
  if (!isAuthenticated) {
    router.push("/login?redirect=/admin");
    return null;
  }

  // Authenticated but not an admin -> 403 Forbidden screen
  if (user?.role !== "admin") {
    return (
      <div className="container mx-auto px-4 py-16 max-w-xl text-center">
        <div className="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-red-100 text-red-600 dark:bg-red-950/50 mb-6">
          <ShieldAlert className="h-8 w-8" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground mb-2">
          403 — Administrator Access Restricted
        </h1>
        <p className="text-sm text-muted-foreground mb-6">
          You are currently signed in as <strong className="text-foreground">{user?.email}</strong> with role{" "}
          <Badge variant="outline" className="capitalize text-xs">{user?.role || "customer"}</Badge>.
          Platform administration features are strictly restricted to authorized platform operators.
        </p>
        <div className="flex justify-center gap-3">
          <Link href="/">
            <Button variant="outline" className="gap-2">
              <ArrowLeft className="h-4 w-4" />
              Return to Storefront
            </Button>
          </Link>
          <Link href="/account">
            <Button className="bg-emerald-600 hover:bg-emerald-700 text-white">
              My Customer Account
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-muted/20">
      {/* Top Banner */}
      <div className="bg-purple-950 text-purple-100 border-b border-purple-900/60 px-4 py-2 text-xs flex items-center justify-between">
        <div className="container mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-4 w-4 text-purple-400" />
            <span className="font-semibold tracking-wide">BASKET PLATFORM ADMIN CONTROLLER</span>
            <Badge className="bg-purple-800 text-[10px] px-1.5 py-0 text-purple-200 border-0">
              Internal Clearance
            </Badge>
          </div>
          <div className="flex items-center gap-4 text-purple-300">
            <span>Operator: <strong>{user?.full_name}</strong></span>
            <Link href="/" className="hover:text-white underline">
              View Public Storefront
            </Link>
          </div>
        </div>
      </div>

      <div className="container mx-auto px-4 sm:px-6 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          {/* Admin Sidebar Navigation */}
          <aside className="lg:col-span-1 space-y-2">
            <div className="rounded-xl border bg-card p-4 shadow-xs">
              <div className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-3 px-2">
                Operations Desk
              </div>
              <nav className="space-y-1 text-sm font-medium">
                <Link
                  href="/admin"
                  className="flex items-center justify-between px-3 py-2 rounded-lg bg-purple-50 text-purple-700 dark:bg-purple-950/50 dark:text-purple-300"
                >
                  <div className="flex items-center gap-2.5">
                    <BarChart3 className="h-4 w-4" />
                    Overview & KPIs
                  </div>
                  <ChevronRight className="h-4 w-4 text-purple-400" />
                </Link>
                <div className="pt-2 pb-1 text-xs font-bold text-muted-foreground uppercase tracking-wider px-2">
                  Marketplace Governance
                </div>
                <Link
                  href="/admin"
                  className="flex items-center gap-2.5 px-3 py-2 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                >
                  <Store className="h-4 w-4" />
                  Retailers & Onboarding
                </Link>
                <Link
                  href="/products"
                  className="flex items-center gap-2.5 px-3 py-2 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                >
                  <LayoutGrid className="h-4 w-4" />
                  Catalogue Explorer
                </Link>
                <Link
                  href="/orders"
                  className="flex items-center gap-2.5 px-3 py-2 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                >
                  <ShoppingBag className="h-4 w-4" />
                  Orders & Shipments
                </Link>
              </nav>
            </div>
          </aside>

          {/* Admin Main Viewport */}
          <main className="lg:col-span-4">{children}</main>
        </div>
      </div>
    </div>
  );
}
