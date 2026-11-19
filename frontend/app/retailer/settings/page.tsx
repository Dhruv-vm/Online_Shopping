"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Settings,
  ArrowLeft,
  Clock,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  Save,
  Power,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiClient } from "@/lib/api/client";
import type { RetailerProfile } from "@/types";

export default function RetailerSettingsPage() {
  const [profile, setProfile] = useState<RetailerProfile | null>(null);
  const [isOpen, setIsOpen] = useState(true);
  const [hours, setHours] = useState("Mon - Sat: 9:00 AM - 9:00 PM, Sun: 10:00 AM - 6:00 PM");
  const [policies, setPolicies] = useState("Standard 7-day hassle-free replacement on defective items. All items checked before dispatch.");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    apiClient
      .getRetailerProfile()
      .then((data) => {
        if (!mounted) return;
        setProfile(data);
        setIsOpen(data.is_open);
        if (data.business_hours) {
          if (typeof data.business_hours === "string") {
            setHours(data.business_hours);
          } else if (data.business_hours.general) {
            setHours(data.business_hours.general);
          } else {
            setHours(JSON.stringify(data.business_hours));
          }
        }
        if (data.policies) {
          if (typeof data.policies === "string") {
            setPolicies(data.policies);
          } else if (data.policies.return_policy) {
            setPolicies(data.policies.return_policy);
          } else {
            setPolicies(JSON.stringify(data.policies));
          }
        }
      })
      .catch((err: unknown) => {
        if (mounted) setErrorMsg(err instanceof Error ? err.message : "Failed to load store settings.");
      })
      .finally(() => {
        if (mounted) setIsLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      const updated = await apiClient.updateRetailerProfile({
        is_open: isOpen,
        business_hours: { general: hours },
        policies: { return_policy: policies },
      });
      setProfile(updated);
      setSuccessMsg("Operating settings saved successfully.");
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to save settings.");
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="p-8 text-center text-sm text-muted-foreground">
        Loading store operating settings...
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center gap-3">
        <Link href="/retailer">
          <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Settings className="h-5 w-5 text-blue-600" />
            Store Operating Settings
          </h1>
          <p className="text-xs text-muted-foreground">
            Configure order acceptance status, operational hours, and merchant customer policies.
          </p>
        </div>
      </div>

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

      <form onSubmit={handleSave} className="space-y-6">
        {/* Open / Close toggle */}
        <div className="rounded-xl border bg-card p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b pb-3">
            <div>
              <h2 className="text-sm font-bold text-foreground flex items-center gap-2">
                <Power className="h-4 w-4 text-emerald-600" />
                Store Online Status
              </h2>
              <p className="text-xs text-muted-foreground">
                Control whether your store is live and accepting customer orders on BASKET.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className={`text-xs font-bold ${isOpen ? "text-emerald-600" : "text-amber-600"}`}>
                {isOpen ? "LIVE & OPEN" : "TEMPORARILY CLOSED"}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3 pt-1">
            <input
              type="checkbox"
              id="is_open_toggle"
              checked={isOpen}
              onChange={(e) => setIsOpen(e.target.checked)}
              className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
            />
            <label htmlFor="is_open_toggle" className="text-xs text-foreground font-medium cursor-pointer">
              Accepting orders on marketplace (when unchecked, customers cannot add your store products to basket)
            </label>
          </div>
        </div>

        {/* Operating hours */}
        <div className="rounded-xl border bg-card p-6 shadow-xs space-y-4">
          <h2 className="text-sm font-bold text-foreground border-b pb-2 flex items-center gap-2">
            <Clock className="h-4 w-4 text-blue-600" />
            Operating & Dispatch Schedule
          </h2>

          <div>
            <label className="text-xs font-semibold text-muted-foreground block mb-1">
              Store & Fulfillment Hours
            </label>
            <Input
              type="text"
              value={hours}
              onChange={(e) => setHours(e.target.value)}
              placeholder="e.g. Mon - Sat: 9:00 AM - 9:00 PM"
              className="text-xs"
            />
            <span className="text-[10px] text-muted-foreground">
              Displayed on your public store profile to set customer delivery expectations.
            </span>
          </div>
        </div>

        {/* Policies */}
        <div className="rounded-xl border bg-card p-6 shadow-xs space-y-4">
          <h2 className="text-sm font-bold text-foreground border-b pb-2 flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-purple-600" />
            Store Return & Warranty Policies
          </h2>

          <div>
            <label className="text-xs font-semibold text-muted-foreground block mb-1">
              Customer Guarantee & Return Policy
            </label>
            <textarea
              rows={3}
              value={policies}
              onChange={(e) => setPolicies(e.target.value)}
              placeholder="Details on returns, replacements, and merchant quality checks..."
              className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-xs shadow-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
          </div>
        </div>

        <div className="flex justify-end gap-3">
          <Link href="/retailer">
            <Button type="button" variant="outline" size="sm">
              Cancel
            </Button>
          </Link>
          <Button
            type="submit"
            disabled={isSaving}
            size="sm"
            className="gap-2 bg-blue-600 hover:bg-blue-700 text-white shadow-xs"
          >
            <Save className="h-4 w-4" />
            {isSaving ? "Saving..." : "Save Operating Settings"}
          </Button>
        </div>
      </form>
    </div>
  );
}
