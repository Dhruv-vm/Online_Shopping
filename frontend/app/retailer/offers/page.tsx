"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Tag,
  PlusCircle,
  Percent,
  Calendar,
  AlertCircle,
  CheckCircle2,
  Trash2,
  RefreshCw,
  Gift,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiClient } from "@/lib/api/client";
import type { RetailerOfferItem, RetailerOfferCreatePayload } from "@/types";

export default function RetailerOffersPage() {
  const [offers, setOffers] = useState<RetailerOfferItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Form state
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [discountType, setDiscountType] = useState<"PERCENTAGE" | "FIXED_AMOUNT">("PERCENTAGE");
  const [discountValue, setDiscountValue] = useState("");
  const [minOrderRupees, setMinOrderRupees] = useState("500");
  const [maxDiscountRupees, setMaxDiscountRupees] = useState("200");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const loadOffers = useCallback(async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const data = await apiClient.listRetailerOffers();
      setOffers(data);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to load store offers.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadOffers();
  }, [loadOffers]);

  const handleCreateOffer = async (e: React.FormEvent) => {
    e.preventDefault();
    const val = parseFloat(discountValue);
    if (isNaN(val) || val <= 0) {
      setFormError("Please enter a valid discount value greater than 0.");
      return;
    }
    if (discountType === "PERCENTAGE" && (val < 1 || val > 90)) {
      setFormError("Percentage discount must be between 1% and 90%.");
      return;
    }

    setIsSubmitting(true);
    setFormError(null);

    try {
      const payload: RetailerOfferCreatePayload = {
        code: code.trim().toUpperCase() || undefined,
        name: name.trim(),
        description: description.trim() || undefined,
        discount_type: discountType,
        discount_value: discountType === "PERCENTAGE" ? Math.round(val * 100) : Math.round(val * 100),
        min_order_paise: Math.round((parseFloat(minOrderRupees) || 0) * 100),
        max_discount_paise: maxDiscountRupees ? Math.round(parseFloat(maxDiscountRupees) * 100) : undefined,
        is_active: true,
      };

      await apiClient.createRetailerOffer(payload);
      setShowCreateModal(false);
      resetForm();
      await loadOffers();
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : "Failed to create offer.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeactivate = async (offerId: string) => {
    if (!confirm("Are you sure you want to deactivate this offer?")) return;
    try {
      await apiClient.deleteRetailerOffer(offerId);
      await loadOffers();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to deactivate offer.");
    }
  };

  const resetForm = () => {
    setCode("");
    setName("");
    setDescription("");
    setDiscountValue("");
    setMinOrderRupees("500");
    setMaxDiscountRupees("200");
    setFormError(null);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Tag className="h-6 w-6 text-blue-600" />
            Offers & Store Discounts
          </h1>
          <p className="text-sm text-muted-foreground">
            Create promotional codes, seasonal discounts, and basket value thresholds for your store.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={loadOffers}
            disabled={isLoading}
            className="gap-2"
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Button
            size="sm"
            onClick={() => setShowCreateModal(true)}
            className="bg-blue-600 hover:bg-blue-700 text-white gap-2 shadow-xs"
          >
            <PlusCircle className="h-4 w-4" />
            Create Store Offer
          </Button>
        </div>
      </div>

      {errorMsg && (
        <div className="p-4 rounded-xl border border-red-500/30 bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 text-sm flex items-center gap-3">
          <AlertCircle className="h-5 w-5 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Offers Grid */}
      {isLoading ? (
        <div className="p-12 text-center text-muted-foreground space-y-3 border rounded-xl bg-card">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-blue-600 border-r-transparent align-[-0.125em]" />
          <p className="text-sm">Loading store offers from database...</p>
        </div>
      ) : offers.length === 0 ? (
        <div className="p-12 text-center text-muted-foreground space-y-3 border border-dashed rounded-xl bg-card">
          <Gift className="h-10 w-10 mx-auto text-muted-foreground/60" />
          <h3 className="font-semibold text-foreground text-base">No Active Offers Configured</h3>
          <p className="text-sm max-w-sm mx-auto">
            Create percentage discounts or coupon codes to drive customer conversions and reward repeat shoppers.
          </p>
          <Button
            size="sm"
            onClick={() => setShowCreateModal(true)}
            className="bg-blue-600 hover:bg-blue-700 text-white gap-2 mt-2"
          >
            <PlusCircle className="h-4 w-4" /> Create First Offer
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {offers.map((offer) => (
            <div
              key={offer.id}
              className="rounded-xl border bg-card p-5 shadow-xs flex flex-col justify-between space-y-4 hover:border-blue-500/40 transition-colors"
            >
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    {offer.code && (
                      <span className="font-mono font-bold text-xs bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200 px-2.5 py-1 rounded-md border border-blue-200 dark:border-blue-800">
                        {offer.code}
                      </span>
                    )}
                    <span className="font-semibold text-foreground text-sm">{offer.name}</span>
                  </div>
                  <Badge variant={offer.is_active ? "default" : "secondary"}>
                    {offer.is_active ? "Active" : "Inactive"}
                  </Badge>
                </div>

                {offer.description && (
                  <p className="text-xs text-muted-foreground line-clamp-2">
                    {offer.description}
                  </p>
                )}

                <div className="pt-2 grid grid-cols-2 gap-2 text-xs">
                  <div className="p-2 rounded bg-muted/40 space-y-0.5">
                    <span className="text-muted-foreground block text-[10px] uppercase font-bold">Benefit</span>
                    <span className="font-bold text-emerald-600 dark:text-emerald-400 font-mono">
                      {offer.discount_type === "PERCENTAGE"
                        ? `${(offer.discount_value / 100).toFixed(0)}% OFF`
                        : `₹${(offer.discount_value / 100).toFixed(2)} OFF`}
                    </span>
                  </div>
                  <div className="p-2 rounded bg-muted/40 space-y-0.5">
                    <span className="text-muted-foreground block text-[10px] uppercase font-bold">Min Order</span>
                    <span className="font-mono font-semibold">
                      ₹{(offer.min_order_paise / 100).toFixed(0)}
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between text-xs pt-2 border-t text-muted-foreground">
                <div className="flex items-center gap-1.5">
                  <Calendar className="h-3.5 w-3.5" />
                  <span>
                    Valid until {offer.valid_to ? new Date(offer.valid_to).toLocaleDateString() : "No Expiry"}
                  </span>
                </div>
                {offer.is_active && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => handleDeactivate(offer.id)}
                    className="text-red-600 hover:text-red-700 hover:bg-red-50 text-xs h-7 px-2 gap-1"
                  >
                    <Trash2 className="h-3.5 w-3.5" /> Deactivate
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Modal Dialog */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="bg-card border rounded-2xl p-6 max-w-lg w-full space-y-4 shadow-xl">
            <div className="flex items-center justify-between border-b pb-3">
              <h3 className="font-bold text-foreground text-lg flex items-center gap-2">
                <PlusCircle className="h-5 w-5 text-blue-600" />
                Create New Store Offer
              </h3>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowCreateModal(false)}
                className="h-8 w-8 p-0"
              >
                ✕
              </Button>
            </div>

            {formError && (
              <div className="p-3 rounded-lg border border-red-500/30 bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 text-xs flex items-center gap-2">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{formError}</span>
              </div>
            )}

            <form onSubmit={handleCreateOffer} className="space-y-3 text-xs">
              <div>
                <label className="font-semibold block mb-1">Offer Title *</label>
                <Input
                  placeholder="e.g. Weekend Flash Sale 15% Off"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold block mb-1">Coupon Code (Optional)</label>
                  <Input
                    placeholder="e.g. SAVE15"
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    className="font-mono uppercase"
                  />
                </div>
                <div>
                  <label className="font-semibold block mb-1">Discount Type *</label>
                  <select
                    className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs transition-colors"
                    value={discountType}
                    onChange={(e) => setDiscountType(e.target.value as "PERCENTAGE" | "FIXED_AMOUNT")}
                  >
                    <option value="PERCENTAGE">Percentage (%)</option>
                    <option value="FIXED_AMOUNT">Fixed Amount (₹)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="font-semibold block mb-1">
                  {discountType === "PERCENTAGE" ? "Discount Percentage (%) *" : "Discount Amount (₹) *"}
                </label>
                <Input
                  type="number"
                  placeholder={discountType === "PERCENTAGE" ? "e.g. 15" : "e.g. 150"}
                  value={discountValue}
                  onChange={(e) => setDiscountValue(e.target.value)}
                  required
                  min="1"
                  max={discountType === "PERCENTAGE" ? "90" : "10000"}
                  className="font-mono text-sm"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold block mb-1">Minimum Order Value (₹)</label>
                  <Input
                    type="number"
                    min="0"
                    placeholder="500"
                    value={minOrderRupees}
                    onChange={(e) => setMinOrderRupees(e.target.value)}
                    className="font-mono text-sm"
                  />
                </div>
                <div>
                  <label className="font-semibold block mb-1">Max Discount Cap (₹)</label>
                  <Input
                    type="number"
                    min="0"
                    placeholder="300"
                    value={maxDiscountRupees}
                    onChange={(e) => setMaxDiscountRupees(e.target.value)}
                    className="font-mono text-sm"
                  />
                </div>
              </div>

              <div>
                <label className="font-semibold block mb-1">Description (Optional)</label>
                <Input
                  placeholder="e.g. Valid on all fashion and electronics items."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowCreateModal(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={isSubmitting}
                  className="bg-blue-600 hover:bg-blue-700 text-white"
                >
                  {isSubmitting ? "Creating..." : "Save & Activate Offer"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
