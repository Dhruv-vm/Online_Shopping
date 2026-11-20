"use client";

import React, { useEffect, useState } from "react";
import {
  AlertCircle,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Loader2,
  PackageCheck,
  PackageX,
  RefreshCw,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  Star,
  Store,
  Tag,
  TrendingDown,
  TrendingUp,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { apiClient, ApiClientError } from "@/lib/api/client";
import { formatPrice } from "@/lib/utils";
import type {
  CartItem,
  SubstituteItem,
  SubstituteListResponse,
  SubstituteType,
} from "@/types";

interface SubstituteModalProps {
  isOpen: boolean;
  onClose: () => void;
  // If invoked from cart
  cartItem?: CartItem | null;
  // If invoked from PDP
  listingId?: string | null;
  productName?: string | null;
  onReplaced?: (replacedItemId: string, newItemId: string) => void;
  onAddToCart?: (listingId: string) => Promise<void>;
}

const SUBSTITUTE_TYPE_TABS: { label: string; value: SubstituteType | "ALL" }[] = [
  { label: "All Alternatives", value: "ALL" },
  { label: "Closest Match", value: "CLOSEST_MATCH" },
  { label: "Budget Friendly", value: "BUDGET_FRIENDLY" },
  { label: "Better Value", value: "BETTER_VALUE" },
  { label: "Premium Upgrade", value: "PREMIUM_UPGRADE" },
  { label: "Available Now", value: "AVAILABLE_NOW" },
];

export function SubstituteModal({
  isOpen,
  onClose,
  cartItem,
  listingId,
  productName,
  onReplaced,
  onAddToCart,
}: SubstituteModalProps) {
  const [activeTab, setActiveTab] = useState<SubstituteType | "ALL">("ALL");
  const [data, setData] = useState<SubstituteListResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Replacement action state
  const [replacingListingId, setReplacingListingId] = useState<string | null>(null);
  const [replaceSuccessMsg, setReplaceSuccessMsg] = useState<string | null>(null);
  const [expandedSpecIds, setExpandedSpecIds] = useState<Record<string, boolean>>({});

  const targetListingId = cartItem?.listing_id || listingId;

  useEffect(() => {
    if (!isOpen || !targetListingId) {
      setData(null);
      setError(null);
      setReplaceSuccessMsg(null);
      return;
    }

    let isMounted = true;
    const fetchSubstitutes = async () => {
      setIsLoading(true);
      setError(null);
      try {
        let resp: SubstituteListResponse;
        if (cartItem) {
          resp = await apiClient.getCartItemSubstitutes(cartItem.id);
        } else {
          resp = await apiClient.getListingSubstitutes(targetListingId);
        }
        if (isMounted) {
          setData(resp);
        }
      } catch (err: unknown) {
        if (isMounted) {
          if (err instanceof ApiClientError) {
            setError(err.message || "Failed to find product alternatives.");
          } else {
            setError("Could not load alternatives at this time.");
          }
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    fetchSubstitutes();

    return () => {
      isMounted = false;
    };
  }, [isOpen, targetListingId, cartItem]);

  if (!isOpen) return null;

  const handleToggleSpecs = (listingId: string) => {
    setExpandedSpecIds((prev) => ({
      ...prev,
      [listingId]: !prev[listingId],
    }));
  };

  const handleReplace = async (sub: SubstituteItem) => {
    if (!cartItem) return;
    setReplacingListingId(sub.listing_id);
    setError(null);
    setReplaceSuccessMsg(null);

    try {
      const resp = await apiClient.replaceCartItem(cartItem.id, {
        new_listing_id: sub.listing_id,
        quantity: cartItem.quantity,
      });

      setReplaceSuccessMsg(
        `Replaced with '${sub.product_name}'. Your basket totals and delivery estimates have been updated.`
      );

      if (onReplaced) {
        onReplaced(resp.replaced_item_id, resp.new_item_id);
      }

      setTimeout(() => {
        onClose();
      }, 1500);
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setError(err.message || "Failed to replace item.");
      } else {
        setError("An unexpected error occurred while replacing the item.");
      }
    } finally {
      setReplacingListingId(null);
    }
  };

  const handleAddAlternative = async (sub: SubstituteItem) => {
    if (!onAddToCart) return;
    setReplacingListingId(sub.listing_id);
    setError(null);
    try {
      await onAddToCart(sub.listing_id);
      setReplaceSuccessMsg(`Added '${sub.product_name}' to your basket.`);
      setTimeout(() => {
        onClose();
      }, 1200);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to add to basket.");
    } finally {
      setReplacingListingId(null);
    }
  };

  // Filter substitutes according to active tab
  const filteredSubstitutes = (data?.substitutes || []).filter((item) => {
    if (activeTab === "ALL") return true;
    return (
      item.substitute_type === activeTab ||
      item.applicable_types?.includes(activeTab)
    );
  });

  const getBadgeStyle = (type: SubstituteType) => {
    switch (type) {
      case "CLOSEST_MATCH":
        return "bg-blue-500/10 text-blue-700 dark:text-blue-300 border-blue-500/30";
      case "BUDGET_FRIENDLY":
        return "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30";
      case "BETTER_VALUE":
        return "bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-500/30";
      case "PREMIUM_UPGRADE":
        return "bg-purple-500/10 text-purple-700 dark:text-purple-300 border-purple-500/30";
      case "AVAILABLE_NOW":
        return "bg-teal-500/10 text-teal-700 dark:text-teal-300 border-teal-500/30";
      default:
        return "bg-muted text-muted-foreground";
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="relative w-full max-w-4xl max-h-[90vh] bg-background border rounded-2xl shadow-2xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-5 py-4 border-b flex items-center justify-between bg-muted/20 shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="h-9 w-9 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-600">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-base sm:text-lg font-bold text-foreground flex items-center gap-2">
                Substitute Intelligence
                {data && (
                  <Badge variant="secondary" className="text-[11px] font-semibold">
                    {data.total_count} {data.total_count === 1 ? "option" : "options"}
                  </Badge>
                )}
              </h2>
              <p className="text-xs text-muted-foreground line-clamp-1">
                Comparing alternatives for{" "}
                <span className="font-semibold text-foreground">
                  {cartItem?.product_name || productName || data?.original_product_name || "selected product"}
                </span>
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="h-8 w-8 rounded-lg flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Filter Chips Bar */}
        <div className="px-5 py-2.5 border-b bg-background overflow-x-auto shrink-0 flex items-center gap-1.5 scrollbar-none">
          {SUBSTITUTE_TYPE_TABS.map((tab) => {
            const isActive = activeTab === tab.value;
            return (
              <button
                key={tab.value}
                onClick={() => setActiveTab(tab.value)}
                className={`px-3 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap transition-all ${
                  isActive
                    ? "bg-foreground text-background shadow-xs"
                    : "bg-muted/60 text-muted-foreground hover:bg-muted hover:text-foreground"
                }`}
              >
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Success / Error Alerts */}
        {replaceSuccessMsg && (
          <div className="mx-5 mt-4 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center gap-2.5 text-xs text-emerald-700 dark:text-emerald-300 font-medium animate-in fade-in">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
            <span>{replaceSuccessMsg}</span>
          </div>
        )}

        {error && (
          <div className="mx-5 mt-4 p-3 rounded-xl bg-red-500/10 border border-red-500/30 flex items-center gap-2.5 text-xs text-red-700 dark:text-red-300 font-medium">
            <AlertCircle className="h-4 w-4 shrink-0 text-red-600" />
            <span>{error}</span>
          </div>
        )}

        {/* Content Body */}
        <div className="p-5 overflow-y-auto space-y-4 flex-1">
          {isLoading ? (
            <div className="py-20 flex flex-col items-center justify-center space-y-3">
              <Loader2 className="h-8 w-8 animate-spin text-amber-500" />
              <p className="text-xs text-muted-foreground font-medium">
                Analyzing verified marketplace listings, specifications, and prices...
              </p>
            </div>
          ) : filteredSubstitutes.length === 0 ? (
            <div className="py-16 text-center space-y-3">
              <div className="h-12 w-12 rounded-2xl bg-muted/60 border mx-auto flex items-center justify-center text-muted-foreground/60">
                <PackageX className="h-6 w-6" />
              </div>
              <p className="text-sm font-bold text-foreground">
                No substitutes found for this filter
              </p>
              <p className="text-xs text-muted-foreground max-w-sm mx-auto">
                No alternative listings currently match the &apos;{activeTab}&apos; criteria.
                Try selecting &apos;All Alternatives&apos; to explore available options.
              </p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setActiveTab("ALL")}
                className="text-xs font-semibold"
              >
                Reset Filter
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              {filteredSubstitutes.map((sub) => {
                const isReplacing = replacingListingId === sub.listing_id;
                const isExpanded = !!expandedSpecIds[sub.listing_id];
                const isCheaper = sub.price_diff_paise < 0;
                const isMoreExpensive = sub.price_diff_paise > 0;

                return (
                  <div
                    key={sub.listing_id}
                    className="rounded-xl border bg-card p-4 sm:p-5 space-y-3.5 hover:border-foreground/20 transition-all shadow-2xs"
                  >
                    {/* Top Row: Tags & Match Quality */}
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <Badge
                          variant="outline"
                          className={`text-[11px] font-bold ${getBadgeStyle(
                            sub.substitute_type
                          )}`}
                        >
                          {sub.substitute_type.replace(/_/g, " ")}
                        </Badge>

                        {/* Additional types */}
                        {sub.applicable_types
                          ?.filter((t) => t !== sub.substitute_type)
                          .slice(0, 2)
                          .map((t) => (
                            <span
                              key={t}
                              className="text-[10px] font-medium bg-muted px-2 py-0.5 rounded-full text-muted-foreground"
                            >
                              {t.replace(/_/g, " ")}
                            </span>
                          ))}
                      </div>

                      <div className="flex items-center gap-2">
                        {sub.is_in_stock ? (
                          <span className="flex items-center gap-1 text-[11px] font-semibold text-emerald-600 dark:text-emerald-400">
                            <CheckCircle2 className="h-3.5 w-3.5" />
                            {sub.available_stock > 5
                              ? "In Stock"
                              : `Only ${sub.available_stock} Left`}
                          </span>
                        ) : (
                          <span className="flex items-center gap-1 text-[11px] font-semibold text-red-600">
                            <AlertCircle className="h-3.5 w-3.5" />
                            Out of Stock
                          </span>
                        )}
                        <span className="text-[11px] font-mono text-muted-foreground">
                          {Math.round(sub.similarity_score * 100)}% match
                        </span>
                      </div>
                    </div>

                    {/* Main Info Grid */}
                    <div className="flex flex-col sm:flex-row items-start gap-4">
                      {/* Image Thumbnail */}
                      <div className="h-20 w-20 shrink-0 rounded-xl bg-muted/60 border overflow-hidden flex items-center justify-center">
                        {sub.primary_image_url ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            src={sub.primary_image_url}
                            alt={sub.product_name}
                            className="h-full w-full object-cover object-center"
                          />
                        ) : (
                          <PackageCheck className="h-8 w-8 text-muted-foreground/40" />
                        )}
                      </div>

                      {/* Product Details */}
                      <div className="flex-1 space-y-1">
                        <h3 className="font-bold text-sm text-foreground hover:text-emerald-700 transition-colors">
                          {sub.product_name}
                        </h3>

                        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                          <span>
                            Brand: <strong className="text-foreground">{sub.brand}</strong>
                          </span>
                          <span>•</span>
                          <span className="flex items-center gap-1">
                            <Store className="h-3 w-3 text-muted-foreground" />
                            Seller: <span className="font-medium text-foreground">{sub.retailer_name}</span>
                          </span>
                          <span className="flex items-center gap-1 text-amber-600 dark:text-amber-400 font-semibold">
                            <Star className="h-3 w-3 fill-amber-500 text-amber-500" />
                            {sub.retailer_rating.toFixed(1)}
                          </span>
                          {sub.retailer_verification_status === "VERIFIED" && (
                            <span className="flex items-center gap-0.5 text-emerald-600 dark:text-emerald-400 text-[11px]">
                              <ShieldCheck className="h-3 w-3" />
                              Verified
                            </span>
                          )}
                        </div>

                        {/* Reason / Recommendation Callout */}
                        <div className="pt-1.5 text-xs text-muted-foreground/90 italic">
                          &ldquo;{sub.reason}&rdquo;
                        </div>
                      </div>

                      {/* Pricing and Action Button */}
                      <div className="flex sm:flex-col items-center sm:items-end justify-between w-full sm:w-auto gap-3 pt-2 sm:pt-0 border-t sm:border-0 shrink-0">
                        <div className="text-left sm:text-right">
                          <div className="text-lg font-extrabold text-foreground">
                            {formatPrice(sub.selling_price_paise)}
                          </div>
                          {isCheaper && (
                            <div className="flex items-center gap-1 text-xs font-bold text-emerald-600 dark:text-emerald-400">
                              <TrendingDown className="h-3.5 w-3.5" />
                              Save {formatPrice(Math.abs(sub.price_diff_paise))} ({sub.savings_percentage}%)
                            </div>
                          )}
                          {isMoreExpensive && (
                            <div className="flex items-center gap-1 text-xs font-semibold text-purple-600 dark:text-purple-400">
                              <TrendingUp className="h-3.5 w-3.5" />
                              +{formatPrice(sub.price_diff_paise)}
                            </div>
                          )}
                        </div>

                        {/* Primary Button */}
                        {cartItem ? (
                          <Button
                            size="sm"
                            onClick={() => handleReplace(sub)}
                            disabled={isReplacing || !sub.is_in_stock}
                            className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs h-9 px-4 shrink-0"
                          >
                            {isReplacing ? (
                              <>
                                <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                                Replacing...
                              </>
                            ) : (
                              <>
                                <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
                                Replace in Basket
                              </>
                            )}
                          </Button>
                        ) : onAddToCart ? (
                          <Button
                            size="sm"
                            onClick={() => handleAddAlternative(sub)}
                            disabled={isReplacing || !sub.is_in_stock}
                            className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs h-9 px-4 shrink-0"
                          >
                            {isReplacing ? (
                              <>
                                <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                                Adding...
                              </>
                            ) : (
                              <>
                                <ShoppingBag className="h-3.5 w-3.5 mr-1.5" />
                                Add to Basket
                              </>
                            )}
                          </Button>
                        ) : (
                          <a
                            href={`/products/${sub.product_slug || sub.product_id}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-input bg-background hover:bg-muted text-xs font-semibold text-foreground transition-colors h-9"
                          >
                            <span>View Product</span>
                            <ExternalLink className="h-3.5 w-3.5" />
                          </a>
                        )}
                      </div>
                    </div>

                    {/* Specification Highlights Preview */}
                    <div className="pt-1 flex flex-wrap items-center gap-1.5 text-[11px]">
                      {sub.matching_specs?.slice(0, 3).map((spec, i) => (
                        <span
                          key={i}
                          className="flex items-center gap-1 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300 px-2 py-0.5 rounded font-medium"
                        >
                          <Check className="h-3 w-3 text-emerald-600" />
                          {spec}
                        </span>
                      ))}
                      {sub.differing_specs?.slice(0, 2).map((spec, i) => (
                        <span
                          key={i}
                          className="flex items-center gap-1 bg-muted px-2 py-0.5 rounded text-muted-foreground"
                        >
                          <Tag className="h-3 w-3" />
                          {spec}
                        </span>
                      ))}

                      {/* Expand Button */}
                      {(sub.detailed_comparisons?.length > 0 ||
                        (sub.differing_specs && sub.differing_specs.length > 2)) && (
                        <button
                          type="button"
                          onClick={() => handleToggleSpecs(sub.listing_id)}
                          className="text-[11px] font-semibold text-emerald-700 dark:text-emerald-400 hover:underline flex items-center gap-0.5 ml-auto"
                        >
                          {isExpanded ? (
                            <>
                              <span>Hide full spec comparison</span>
                              <ChevronUp className="h-3 w-3" />
                            </>
                          ) : (
                            <>
                              <span>Compare all specs</span>
                              <ChevronDown className="h-3 w-3" />
                            </>
                          )}
                        </button>
                      )}
                    </div>

                    {/* Collapsible Detailed Specs Table */}
                    {isExpanded && sub.detailed_comparisons?.length > 0 && (
                      <div className="pt-2 border-t mt-2 text-xs animate-in slide-in-from-top-1 duration-150 space-y-2">
                        <div className="font-semibold text-muted-foreground text-[11px]">
                          Specification Comparison vs Selected Item:
                        </div>
                        <div className="overflow-x-auto rounded-lg border">
                          <table className="w-full text-left text-xs">
                            <thead className="bg-muted/50 text-[11px] font-bold text-muted-foreground border-b">
                              <tr>
                                <th className="p-2">Specification</th>
                                <th className="p-2">Current Item</th>
                                <th className="p-2">Alternative Option</th>
                                <th className="p-2 text-right">Match</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y text-[11px]">
                              {sub.detailed_comparisons.map((spec, idx) => (
                                <tr
                                  key={idx}
                                  className={
                                    spec.is_match
                                      ? "bg-background"
                                      : "bg-amber-500/5"
                                  }
                                >
                                  <td className="p-2 font-medium text-foreground">
                                    {spec.label}
                                  </td>
                                  <td className="p-2 text-muted-foreground">
                                    {String(spec.original_value)}
                                  </td>
                                  <td className="p-2 font-semibold text-foreground">
                                    {String(spec.substitute_value)}
                                  </td>
                                  <td className="p-2 text-right">
                                    {spec.is_match ? (
                                      <span className="inline-flex items-center text-emerald-600 font-bold">
                                        <Check className="h-3.5 w-3.5" />
                                      </span>
                                    ) : (
                                      <span className="text-amber-600 dark:text-amber-400 font-medium">
                                        Different
                                      </span>
                                    )}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                        {sub.compatibility_notes && (
                          <p className="text-[11px] text-muted-foreground">
                            <strong>Note:</strong> {sub.compatibility_notes}
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t bg-muted/20 flex items-center justify-between text-xs text-muted-foreground shrink-0">
          <span>
            Every substitute is backed by live stock and verified seller guarantees.
          </span>
          <Button variant="ghost" size="sm" onClick={onClose} className="text-xs">
            Close
          </Button>
        </div>
      </div>
    </div>
  );
}
