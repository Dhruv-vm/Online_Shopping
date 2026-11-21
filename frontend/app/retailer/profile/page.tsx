"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Save,
  ArrowLeft,
  AlertCircle,
  CheckCircle2,
  Store,
  MapPin,
  Phone,
  Mail,
  FileText,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiClient } from "@/lib/api/client";
import type { RetailerProfile } from "@/types";

export default function RetailerProfileSettingsPage() {
  const [profile, setProfile] = useState<RetailerProfile | null>(null);
  const [description, setDescription] = useState("");
  const [businessAddress, setBusinessAddress] = useState("");
  const [contactPhone, setContactPhone] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [logoUrl, setLogoUrl] = useState("");
  const [isOpen, setIsOpen] = useState(true);

  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    apiClient
      .getRetailerProfile()
      .then((data) => {
        if (!mounted) return;
        setProfile(data);
        setDescription(data.description || "");
        setBusinessAddress(data.business_address || "");
        setContactPhone(data.contact_phone || "");
        setContactEmail(data.contact_email || "");
        setLogoUrl(data.logo_url || "");
        setIsOpen(data.is_open);
      })
      .catch((err: unknown) => {
        if (mounted) {
          setErrorMsg(err instanceof Error ? err.message : "Failed to load profile.");
        }
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
        description,
        business_address: businessAddress,
        contact_phone: contactPhone,
        contact_email: contactEmail,
        logo_url: logoUrl || undefined,
        is_open: isOpen,
      });
      setProfile(updated);
      setSuccessMsg("Store profile and contact settings saved successfully.");
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to save profile.");
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="p-8 text-center text-sm text-muted-foreground">
        Loading store settings...
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
          <h1 className="text-xl font-bold tracking-tight text-foreground">
            Store Profile & Operating Settings
          </h1>
          <p className="text-xs text-muted-foreground">
            Manage your store information, business address, and marketplace operating parameters.
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
        <div className="rounded-xl border bg-card p-6 shadow-xs space-y-4">
          <h2 className="text-sm font-bold text-foreground border-b pb-2 flex items-center gap-2">
            <Store className="h-4 w-4 text-blue-600" />
            General Store Details
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-semibold text-muted-foreground block mb-1">
                Store Name (Canonical)
              </label>
              <Input
                type="text"
                disabled
                value={profile?.name || ""}
                className="bg-muted text-xs cursor-not-allowed"
              />
              <span className="text-[10px] text-muted-foreground">
                Store name can only be changed via administrator support ticket.
              </span>
            </div>

            <div>
              <label className="text-xs font-semibold text-muted-foreground block mb-1">
                Store URL Slug
              </label>
              <Input
                type="text"
                disabled
                value={profile?.slug || ""}
                className="bg-muted font-mono text-xs cursor-not-allowed"
              />
            </div>
          </div>

          <div>
            <label className="text-xs font-semibold text-muted-foreground block mb-1">
              Store Description
            </label>
            <textarea
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Tell customers about your products, heritage, and specialty..."
              className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-xs shadow-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-muted-foreground block mb-1">
              Store Logo Image URL
            </label>
            <Input
              type="url"
              value={logoUrl}
              onChange={(e) => setLogoUrl(e.target.value)}
              placeholder="https://images.basket.local/stores/logo.jpg"
              className="text-xs"
            />
          </div>
        </div>

        <div className="rounded-xl border bg-card p-6 shadow-xs space-y-4">
          <h2 className="text-sm font-bold text-foreground border-b pb-2 flex items-center gap-2">
            <MapPin className="h-4 w-4 text-emerald-600" />
            Business Address & Warehouse Location
          </h2>

          <div>
            <label className="text-xs font-semibold text-muted-foreground block mb-1">
              Registered Business / Dispatch Address
            </label>
            <textarea
              rows={2}
              required
              value={businessAddress}
              onChange={(e) => setBusinessAddress(e.target.value)}
              placeholder="Complete shop / warehouse address with pin code..."
              className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-xs shadow-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-semibold text-muted-foreground block mb-1">
                Store Contact Phone
              </label>
              <Input
                type="tel"
                value={contactPhone}
                onChange={(e) => setContactPhone(e.target.value)}
                placeholder="+919876543210"
                className="text-xs"
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-muted-foreground block mb-1">
                Store Inquiries Email
              </label>
              <Input
                type="email"
                value={contactEmail}
                onChange={(e) => setContactEmail(e.target.value)}
                placeholder="store@domain.com"
                className="text-xs"
              />
            </div>
          </div>
        </div>

        <div className="rounded-xl border bg-card p-6 shadow-xs space-y-4">
          <h2 className="text-sm font-bold text-foreground border-b pb-2 flex items-center gap-2">
            <FileText className="h-4 w-4 text-purple-600" />
            Store Status & Availability
          </h2>

          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              id="is_open_check"
              checked={isOpen}
              onChange={(e) => setIsOpen(e.target.checked)}
              className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <label htmlFor="is_open_check" className="text-xs text-foreground font-medium cursor-pointer">
              Store is currently Open (accepting orders from customers on the marketplace)
            </label>
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
            {isSaving ? "Saving..." : "Save Settings"}
          </Button>
        </div>
      </form>
    </div>
  );
}
