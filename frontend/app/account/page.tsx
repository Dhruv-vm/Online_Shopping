"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth/auth-context";
import { apiClient, ApiClientError } from "@/lib/api/client";
import { ProtectedRoute } from "@/components/auth/protected-route";
import { AccountNav } from "@/components/account/account-nav";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
} from "lucide-react";

export default function AccountOverviewPage() {
  const router = useRouter();
  const { user, logout } = useAuth();
  const [isLoggingOutAll, setIsLoggingOutAll] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

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
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Link href="/account/addresses" className="block group">
                <Card className="h-full hover:border-emerald-600/50 hover:shadow-md transition-all cursor-pointer">
                  <CardContent className="p-6 flex items-start gap-4">
                    <div className="p-3 rounded-xl bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 group-hover:scale-105 transition-transform">
                      <MapPin className="h-6 w-6" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-foreground group-hover:text-emerald-600 transition-colors">
                        Saved Addresses
                      </h3>
                      <p className="text-xs text-muted-foreground mt-1">
                        Manage delivery destinations and default shipping address
                      </p>
                    </div>
                  </CardContent>
                </Card>
              </Link>

              <Card className="h-full">
                <CardContent className="p-6 flex items-start gap-4">
                  <div className="p-3 rounded-xl bg-muted text-muted-foreground">
                    <Shield className="h-6 w-6" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-foreground">Security & Sessions</h3>
                    <p className="text-xs text-muted-foreground mt-1">
                      Protected with Argon2id hashing & HttpOnly cookie tokens
                    </p>
                  </div>
                </CardContent>
              </Card>
            </div>

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
