"use client";

import React, { useState, Suspense } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth/auth-context";
import { ApiClientError } from "@/lib/api/client";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Store,
  Lock,
  Mail,
  User as UserIcon,
  Phone,
  Eye,
  EyeOff,
  AlertCircle,
  Loader2,
  MapPin,
  Building,
} from "lucide-react";

function RetailerRegisterForm() {
  const router = useRouter();
  const { registerRetailer, isAuthenticated, user } = useAuth();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [storeName, setStoreName] = useState("");
  const [stateCode, setStateCode] = useState("KA");
  const [businessAddress, setBusinessAddress] = useState("");
  const [description, setDescription] = useState("");

  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  React.useEffect(() => {
    if (isAuthenticated && user?.role === "retailer") {
      router.replace("/retailer");
    }
  }, [isAuthenticated, user?.role, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    const trimmedName = fullName.trim();
    const trimmedEmail = email.trim();
    const trimmedPhone = phone.trim();
    const trimmedStore = storeName.trim();
    const trimmedAddress = businessAddress.trim();

    if (!trimmedName || trimmedName.length < 2) {
      setErrorMessage("Owner name must be at least 2 characters long.");
      return;
    }
    if (!trimmedStore || trimmedStore.length < 2) {
      setErrorMessage("Store name must be at least 2 characters long.");
      return;
    }
    if (!trimmedAddress || trimmedAddress.length < 5) {
      setErrorMessage("Please enter a valid registered business address.");
      return;
    }
    if (password.length < 8) {
      setErrorMessage("Password must be at least 8 characters long.");
      return;
    }
    if (password !== confirmPassword) {
      setErrorMessage("Passwords do not match.");
      return;
    }

    setIsLoading(true);
    try {
      await registerRetailer({
        email: trimmedEmail,
        password,
        full_name: trimmedName,
        phone: trimmedPhone,
        store_name: trimmedStore,
        state: stateCode.trim().toUpperCase(),
        business_address: trimmedAddress,
        description: description.trim() || undefined,
      });
      router.push("/retailer");
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        if (err.code === "EMAIL_ALREADY_EXISTS" || err.status === 409) {
          setErrorMessage("An account with this email address already exists.");
        } else {
          setErrorMessage(err.message || "Failed to complete retailer onboarding.");
        }
      } else {
        setErrorMessage("An unexpected network error occurred. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Card className="w-full max-w-xl shadow-lg border-muted">
      <CardHeader className="text-center pb-4">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-600 text-white mb-2 shadow-sm">
          <Store className="h-7 w-7" />
        </div>
        <CardTitle className="text-2xl font-bold tracking-tight">
          Partner Retailer Onboarding
        </CardTitle>
        <CardDescription className="text-xs">
          Open your digital storefront on BASKET and reach multi-category shoppers across India.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {errorMessage && (
          <div
            role="alert"
            className="mb-4 flex items-center gap-2 rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-xs text-red-600 dark:text-red-400"
          >
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="rounded-lg border bg-muted/20 p-3.5 space-y-3">
            <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider block">
              1. Store & Business Details
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="sm:col-span-2 space-y-1">
                <label className="text-xs font-semibold text-foreground">
                  Store / Trade Name <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <Building className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    required
                    placeholder="e.g. Croma Electronics, Nature Basket"
                    value={storeName}
                    onChange={(e) => setStoreName(e.target.value)}
                    className="pl-9 h-9 text-xs"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-foreground">
                  State <span className="text-red-500">*</span>
                </label>
                <select
                  value={stateCode}
                  onChange={(e) => setStateCode(e.target.value)}
                  className="w-full h-9 rounded-md border border-input bg-background px-2 text-xs"
                >
                  <option value="KA">Karnataka (KA)</option>
                  <option value="MH">Maharashtra (MH)</option>
                  <option value="DL">Delhi (DL)</option>
                  <option value="TN">Tamil Nadu (TN)</option>
                  <option value="TS">Telangana (TS)</option>
                  <option value="UP">Uttar Pradesh (UP)</option>
                  <option value="GJ">Gujarat (GJ)</option>
                  <option value="WB">West Bengal (WB)</option>
                </select>
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-semibold text-foreground">
                Registered Warehouse / Dispatch Address <span className="text-red-500">*</span>
              </label>
              <div className="relative">
                <MapPin className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  required
                  placeholder="Complete business address with pin code..."
                  value={businessAddress}
                  onChange={(e) => setBusinessAddress(e.target.value)}
                  className="pl-9 h-9 text-xs"
                />
              </div>
            </div>
          </div>

          <div className="rounded-lg border bg-muted/20 p-3.5 space-y-3">
            <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider block">
              2. Owner & Login Credentials
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-foreground">
                  Owner Full Name <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <UserIcon className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    required
                    placeholder="Full name"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    className="pl-9 h-9 text-xs"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-foreground">
                  Business Phone <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <Phone className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    required
                    type="tel"
                    placeholder="+919876543210"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    className="pl-9 h-9 text-xs"
                  />
                </div>
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-semibold text-foreground">
                Business Email (Login Username) <span className="text-red-500">*</span>
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  required
                  type="email"
                  placeholder="seller@business.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="pl-9 h-9 text-xs"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-foreground">
                  Password <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <Lock className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    required
                    type={showPassword ? "text" : "password"}
                    placeholder="Min 8 characters"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="pl-9 pr-9 h-9 text-xs"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-2.5 text-muted-foreground hover:text-foreground"
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-foreground">
                  Confirm Password <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <Lock className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    required
                    type={showPassword ? "text" : "password"}
                    placeholder="Confirm password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="pl-9 h-9 text-xs"
                  />
                </div>
              </div>
            </div>
          </div>

          <Button
            type="submit"
            disabled={isLoading}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs h-10 shadow-sm"
          >
            {isLoading ? (
              <span className="flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                Provisioning Store Account...
              </span>
            ) : (
              "Submit Store Registration & Open Merchant Portal"
            )}
          </Button>

          <div className="text-center text-xs text-muted-foreground pt-1">
            Already have a merchant account?{" "}
            <Link
              href="/login?redirect=/retailer"
              className="font-medium text-blue-600 hover:text-blue-700 dark:text-blue-400 hover:underline"
            >
              Sign In to Merchant Desk
            </Link>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

export default function RetailerRegisterPage() {
  return (
    <div className="container mx-auto flex min-h-[calc(100vh-8rem)] items-center justify-center px-4 py-8">
      <Suspense
        fallback={
          <div className="text-center text-sm text-muted-foreground">
            Loading merchant onboarding...
          </div>
        }
      >
        <RetailerRegisterForm />
      </Suspense>
    </div>
  );
}
