"use client";

import React, { useState, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth/auth-context";
import { ApiClientError } from "@/lib/api/client";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ShoppingBasket, Lock, Mail, Eye, EyeOff, AlertCircle, Loader2 } from "lucide-react";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectTarget = searchParams.get("redirect") || "/account";
  const { login, isAuthenticated } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // If already logged in, redirect immediately
  React.useEffect(() => {
    if (isAuthenticated) {
      const safeTarget = redirectTarget.startsWith("/") && !redirectTarget.startsWith("//")
        ? redirectTarget
        : "/account";
      router.replace(safeTarget);
    }
  }, [isAuthenticated, redirectTarget, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      setErrorMessage("Please enter your email address.");
      return;
    }
    if (!password) {
      setErrorMessage("Please enter your password.");
      return;
    }

    setIsLoading(true);
    try {
      await login(trimmedEmail, password);
      const safeTarget = redirectTarget.startsWith("/") && !redirectTarget.startsWith("//")
        ? redirectTarget
        : "/account";
      router.push(safeTarget);
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        if (err.code === "INVALID_CREDENTIALS" || err.status === 401) {
          setErrorMessage("Invalid email or password. Please verify your credentials.");
        } else if (err.code === "LOGIN_RATE_LIMITED" || err.status === 429) {
          setErrorMessage("Too many failed login attempts. For security, please wait 60 seconds before trying again.");
        } else if (err.code === "USER_INACTIVE" || err.status === 403) {
          setErrorMessage("This account has been deactivated. Please contact support.");
        } else {
          setErrorMessage(err.message || "Login failed. Please try again.");
        }
      } else {
        setErrorMessage("Network error: Unable to connect to the authentication server.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="container mx-auto px-4 py-12 sm:py-16 flex items-center justify-center min-h-[calc(100vh-12rem)]">
      <Card className="w-full max-w-md shadow-lg border-muted/50">
        <CardHeader className="space-y-2 text-center pb-6">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-600 text-white shadow-sm">
            <ShoppingBasket className="h-6 w-6" />
          </div>
          <CardTitle className="text-2xl font-bold tracking-tight text-foreground">
            Welcome to BASKET
          </CardTitle>
          <CardDescription className="text-sm text-muted-foreground">
            Sign in to access your saved cart, addresses, and order history
          </CardDescription>
        </CardHeader>

        <CardContent>
          {errorMessage && (
            <div
              role="alert"
              className="mb-6 flex items-start gap-3 rounded-lg border border-red-500/20 bg-red-500/10 p-3.5 text-sm text-red-700 dark:text-red-400"
            >
              <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
              <div className="flex-1 font-medium">{errorMessage}</div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label
                htmlFor="email"
                className="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
              >
                Email Address
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-3 h-4 w-4 text-muted-foreground pointer-events-none" />
                <Input
                  id="email"
                  type="email"
                  autoComplete="email"
                  required
                  placeholder="name@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="pl-9 h-10"
                  disabled={isLoading}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label
                  htmlFor="password"
                  className="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
                >
                  Password
                </label>
              </div>
              <div className="relative">
                <Lock className="absolute left-3 top-3 h-4 w-4 text-muted-foreground pointer-events-none" />
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  required
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="pl-9 pr-10 h-10"
                  disabled={isLoading}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  className="absolute right-3 top-3 text-muted-foreground hover:text-foreground transition-colors"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <Button
              type="submit"
              disabled={isLoading}
              className="w-full h-10 bg-emerald-600 hover:bg-emerald-700 text-white font-medium shadow-sm transition-colors mt-2"
            >
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Signing In...
                </>
              ) : (
                "Sign In"
              )}
            </Button>
          </form>

          <div className="mt-6 text-center text-sm text-muted-foreground">
            Don&apos;t have an account?{" "}
            <Link
              href={`/register${redirectTarget !== "/account" ? `?redirect=${encodeURIComponent(redirectTarget)}` : ""}`}
              className="font-semibold text-emerald-600 hover:text-emerald-700 dark:text-emerald-400 hover:underline"
            >
              Create Account
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="container mx-auto px-4 py-24 flex justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-emerald-600" />
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
