"use client";

import { useEffect, useState, useCallback, use } from "react";
import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import {
  Compass,
  ArrowLeft,
  ShoppingCart,
  Trash2,
  RefreshCw,
  Plus,
  Minus,
  CheckCircle2,
  AlertTriangle,
  Info,
  Layers,
  Sparkles,
  Store,
  Tag,
  Loader2,
  X,
  ExternalLink,
  Package,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { apiClient } from "@/lib/api/client";
import { useCart } from "@/lib/cart/cart-context";
import type {
  MissionDetail,
  MissionItem,
  MissionAlternativeItem,
  MissionAddToCartResponse,
} from "@/types";

const ALLOWED_IMAGE_HOSTS = new Set(["images.unsplash.com"]);

function isValidImageHost(url?: string | null): boolean {
  if (!url) return false;
  if (url.startsWith("/")) return true;
  try {
    const parsed = new URL(url);
    return (
      (parsed.protocol === "https:" || parsed.protocol === "http:") &&
      ALLOWED_IMAGE_HOSTS.has(parsed.hostname)
    );
  } catch {
    return false;
  }
}

function MissionProductImage({
  src,
  alt,
  sizes = "80px",
}: {
  src?: string | null;
  alt: string;
  sizes?: string;
}) {
  const [loadError, setLoadError] = useState(false);

  if (!src || loadError || !isValidImageHost(src)) {
    return (
      <div className="h-full w-full flex flex-col items-center justify-center bg-muted/50 text-muted-foreground/50 p-1 text-center select-none">
        <Package className="h-5 w-5 mb-0.5 opacity-60" />
        <span className="text-[9px] font-medium leading-tight line-clamp-1">{alt}</span>
      </div>
    );
  }

  return (
    <Image
      src={src}
      alt={alt}
      fill
      className="object-cover"
      sizes={sizes}
      onError={() => setLoadError(true)}
    />
  );
}

function formatPrice(paise: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(paise / 100);
}

export default function MissionDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const router = useRouter();
  const resolvedParams = use(params);
  const missionId = resolvedParams.id;
  const { refreshCart } = useCart();

  const [mission, setMission] = useState<MissionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Item modification loading states
  const [updatingItemId, setUpdatingItemId] = useState<string | null>(null);

  // Alternatives Modal State
  const [altModalItem, setAltModalItem] = useState<MissionItem | null>(null);
  const [alternatives, setAlternatives] = useState<MissionAlternativeItem[]>([]);
  const [loadingAlts, setLoadingAlts] = useState(false);
  const [replacingAlt, setReplacingAlt] = useState(false);

  // Add to Cart State
  const [isAddingToCart, setIsAddingToCart] = useState(false);
  const [cartSuccessResponse, setCartSuccessResponse] = useState<MissionAddToCartResponse | null>(null);

  // Delete Mission State
  const [isDeleting, setIsDeleting] = useState(false);
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);

  const fetchMission = useCallback(async () => {
    try {
      const data = await apiClient.getMission(missionId);
      setMission(data);
      setError(null);
    } catch (err: unknown) {
      const apiErr = err as { message?: string };
      setError(apiErr.message || "Failed to load shopping mission.");
    } finally {
      setLoading(false);
    }
  }, [missionId]);

  useEffect(() => {
    fetchMission();
  }, [fetchMission]);

  // Handle item quantity change
  const handleQuantityChange = async (item: MissionItem, newQty: number) => {
    if (newQty < 1 || newQty > 99) return;
    setUpdatingItemId(item.id);
    try {
      const updated = await apiClient.updateMissionItem(missionId, item.id, {
        quantity: newQty,
      });
      setMission(updated);
    } catch (err: unknown) {
      console.error("Failed to update item quantity:", err);
    } finally {
      setUpdatingItemId(null);
    }
  };

  // Handle item toggle inclusion
  const handleToggleItem = async (item: MissionItem) => {
    setUpdatingItemId(item.id);
    try {
      const updated = await apiClient.updateMissionItem(missionId, item.id, {
        is_selected: !item.is_selected,
      });
      setMission(updated);
    } catch (err: unknown) {
      console.error("Failed to toggle item:", err);
    } finally {
      setUpdatingItemId(null);
    }
  };

  // Handle item delete
  const handleDeleteItem = async (item: MissionItem) => {
    setUpdatingItemId(item.id);
    try {
      const updated = await apiClient.deleteMissionItem(missionId, item.id);
      setMission(updated);
    } catch (err: unknown) {
      console.error("Failed to delete item:", err);
    } finally {
      setUpdatingItemId(null);
    }
  };

  // Open Alternatives Modal
  const openAlternativesModal = async (item: MissionItem) => {
    setAltModalItem(item);
    setLoadingAlts(true);
    setAlternatives([]);
    try {
      const alts = await apiClient.getMissionItemAlternatives(missionId, item.id);
      setAlternatives(alts);
    } catch (err) {
      console.error("Failed to fetch alternatives:", err);
    } finally {
      setLoadingAlts(false);
    }
  };

  // Replace item with alternative
  const handleSelectAlternative = async (alt: MissionAlternativeItem) => {
    if (!altModalItem) return;
    setReplacingAlt(true);
    try {
      const updated = await apiClient.replaceMissionItem(missionId, altModalItem.id, {
        new_listing_id: alt.listing_id,
      });
      setMission(updated);
      setAltModalItem(null);
    } catch (err) {
      console.error("Failed to replace item:", err);
    } finally {
      setReplacingAlt(false);
    }
  };

  // Add all selected items to Cart
  const handleAddToCart = async () => {
    if (!mission) return;
    setIsAddingToCart(true);
    try {
      const resp = await apiClient.addMissionToCart(missionId);
      setCartSuccessResponse(resp);
      if (refreshCart) {
        await refreshCart();
      }
    } catch (err: unknown) {
      const apiErr = err as { message?: string };
      alert(apiErr.message || "Failed to add items to cart.");
    } finally {
      setIsAddingToCart(false);
    }
  };

  // Delete Mission
  const handleDeleteMission = async () => {
    setIsDeleting(true);
    try {
      await apiClient.deleteMission(missionId);
      router.push("/missions");
    } catch (err) {
      console.error("Failed to delete mission:", err);
      setIsDeleting(false);
    }
  };

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-16 text-center space-y-4 max-w-4xl">
        <Loader2 className="h-8 w-8 animate-spin text-emerald-600 mx-auto" />
        <h2 className="text-base font-semibold text-foreground">Loading your mission plan...</h2>
        <p className="text-xs text-muted-foreground">Gathering real-time product prices and retailer stock.</p>
      </div>
    );
  }

  if (error || !mission) {
    return (
      <div className="container mx-auto px-4 py-16 text-center space-y-4 max-w-lg">
        <div className="p-4 rounded-xl bg-destructive/10 text-destructive text-sm font-semibold flex items-center justify-center gap-2">
          <AlertTriangle className="h-5 w-5" />
          {error || "Shopping mission not found"}
        </div>
        <Link href="/missions">
          <Button variant="outline" size="sm">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Missions
          </Button>
        </Link>
      </div>
    );
  }

  const selectedCount = mission.items.filter((i) => i.is_selected).length;

  return (
    <div className="container mx-auto space-y-8 px-4 py-6 sm:px-6 max-w-6xl">
      {/* Top Breadcrumb & Action Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b pb-4">
        <div className="space-y-1">
          <Link
            href="/missions"
            className="inline-flex items-center text-xs font-semibold text-muted-foreground hover:text-emerald-700 transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5 mr-1" />
            All Missions
          </Link>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl sm:text-2xl font-extrabold tracking-tight text-foreground">
              {mission.title}
            </h1>
            <Badge
              variant={mission.status === "ACTIVE" ? "default" : "secondary"}
              className="text-xs font-semibold"
            >
              {mission.status}
            </Badge>
          </div>
          {mission.description && (
            <p className="text-xs text-muted-foreground line-clamp-2 max-w-2xl">
              {mission.description}
            </p>
          )}
          <p className="text-xs text-muted-foreground" aria-live="polite">
            {mission.status === "COMPLETED" && mission.completed_order_id ? (
              <>
                Completed{mission.completed_at ? ` on ${new Date(mission.completed_at).toLocaleDateString()}` : ""} ·{" "}
                <Link href={`/orders/${mission.completed_order_id}`} className="underline">view order</Link>
              </>
            ) : mission.carted_at ? (
              `Progress: ${mission.purchased_items_count ?? 0} of ${mission.items_count} items bought in paid orders. The mission completes when one paid order has them all.`
            ) : (
              "Add the mission to your cart and check out to complete it."
            )}
          </p>
        </div>

        <div className="flex items-center gap-2.5 shrink-0">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setConfirmDeleteOpen(true)}
            className="text-destructive hover:bg-destructive/10 border-destructive/30 text-xs h-9"
          >
            <Trash2 className="h-3.5 w-3.5 mr-1.5" />
            Delete Plan
          </Button>

          <Button
            size="sm"
            onClick={handleAddToCart}
            disabled={isAddingToCart || selectedCount === 0}
            className="bg-brand-yellow hover:bg-brand-yellow-dark text-ink font-semibold text-xs h-9 shadow-md"
          >
            {isAddingToCart ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
                Adding to Basket...
              </>
            ) : (
              <>
                <ShoppingCart className="h-3.5 w-3.5 mr-1.5" />
                Add Selected to Basket ({selectedCount})
              </>
            )}
          </Button>
        </div>
      </div>

      {/* KPI Dashboard */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
        <Card className="border shadow-xs bg-card">
          <CardContent className="p-4 space-y-1">
            <span className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground">
              Budget Target
            </span>
            <div className="text-lg sm:text-xl font-extrabold text-foreground">
              {formatPrice(mission.budget_paise)}
            </div>
            <span className="text-[11px] text-muted-foreground block">
              For {mission.people_count} {mission.people_count === 1 ? "person" : "people"}
            </span>
          </CardContent>
        </Card>

        <Card className="border shadow-xs bg-card">
          <CardContent className="p-4 space-y-1">
            <span className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground">
              Plan Total ({selectedCount} items)
            </span>
            <div className="text-lg sm:text-xl font-extrabold text-foreground">
              {formatPrice(mission.total_cost_paise)}
            </div>
            <span className="text-[11px] text-muted-foreground block">
              {selectedCount} of {mission.items_count} items selected
            </span>
          </CardContent>
        </Card>

        <Card className="border shadow-xs bg-card">
          <CardContent className="p-4 space-y-1">
            <span className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground">
              {mission.is_over_budget ? "Budget Shortfall" : "Remaining Budget"}
            </span>
            <div
              className={`text-lg sm:text-xl font-extrabold ${
                mission.is_over_budget
                  ? "text-amber-600 dark:text-amber-400"
                  : "text-emerald-600 dark:text-emerald-400"
              }`}
            >
              {mission.is_over_budget
                ? `+${formatPrice(mission.budget_shortfall_paise)}`
                : formatPrice(mission.remaining_budget_paise)}
            </div>
            <span className="text-[11px] text-muted-foreground block">
              {mission.is_over_budget ? "Exceeds initial budget" : "Available to allocate"}
            </span>
          </CardContent>
        </Card>

        <Card className="border shadow-xs bg-card">
          <CardContent className="p-4 space-y-1">
            <span className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground">
              Stock Availability
            </span>
            <div className="text-lg sm:text-xl font-extrabold text-foreground flex items-center gap-1.5">
              {mission.unavailable_items_count === 0 ? (
                <>
                  <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0" />
                  <span className="text-emerald-700 dark:text-emerald-400 text-sm sm:text-base font-bold">
                    All In Stock
                  </span>
                </>
              ) : (
                <>
                  <AlertTriangle className="h-5 w-5 text-amber-500 shrink-0" />
                  <span className="text-amber-700 dark:text-amber-400 text-sm sm:text-base font-bold">
                    {mission.unavailable_items_count} Out of Stock
                  </span>
                </>
              )}
            </div>
            <span className="text-[11px] text-muted-foreground block">
              Direct from verified retailers
            </span>
          </CardContent>
        </Card>
      </div>

      {/* Rationale & Explanation Banner */}
      <div className="p-4 rounded-xl border bg-emerald-50/60 dark:bg-emerald-950/20 border-emerald-500/20 flex items-start gap-3">
        <Sparkles className="h-5 w-5 text-emerald-600 shrink-0 mt-0.5" />
        <div className="space-y-1 text-xs">
          <h4 className="font-bold text-foreground">Mission Plan Overview</h4>
          <p className="text-muted-foreground leading-relaxed">
            {mission.summary_explanation}
          </p>
        </div>
      </div>

      {/* Grouped Products */}
      <div className="space-y-8">
        {mission.groups.length === 0 ? (
          <div className="text-center py-12 px-4 rounded-2xl border border-dashed bg-muted/20 space-y-4">
            <Compass className="h-10 w-10 text-muted-foreground mx-auto" />
            <div className="space-y-1">
              <h3 className="text-base font-semibold text-foreground">No Matching Products Found</h3>
              <p className="text-xs text-muted-foreground max-w-md mx-auto">
                No active marketplace items currently match this mission&apos;s budget or filters. You can edit your criteria or explore products across our verified sellers.
              </p>
            </div>
            <div className="flex items-center justify-center gap-3 pt-2">
              <Link href="/missions">
                <Button variant="outline" size="sm">
                  <ArrowLeft className="h-4 w-4 mr-2" />
                  Create Another Mission
                </Button>
              </Link>
              <Link href="/search">
                <Button size="sm" className="bg-brand-yellow hover:bg-brand-yellow-dark text-ink">
                  Browse Catalog
                </Button>
              </Link>
            </div>
          </div>
        ) : (
          mission.groups.map((group) => (
            <div key={group.group_name} className="space-y-3">
            <div className="flex items-center justify-between border-b pb-2">
              <div className="flex items-center gap-2">
                <Layers className="h-4 w-4 text-emerald-600" />
                <h3 className="text-base font-bold text-foreground tracking-tight">
                  {group.group_name}
                </h3>
                <Badge variant="outline" className="text-[11px] font-medium">
                  {group.items_count} items
                </Badge>
              </div>
              <div className="text-xs font-semibold text-muted-foreground">
                Subtotal: <span className="text-foreground font-bold">{formatPrice(group.subtotal_paise)}</span>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3">
              {group.items.map((item) => {
                const isItemUpdating = updatingItemId === item.id;

                return (
                  <div
                    key={item.id}
                    className={`flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-4 rounded-xl border bg-card transition-all ${
                      !item.is_selected ? "opacity-60 bg-muted/20" : "hover:border-emerald-500/40"
                    }`}
                  >
                    {/* Left: Checkbox + Image + Details */}
                    <div className="flex items-start gap-3.5 flex-1 min-w-0">
                      <input
                        type="checkbox"
                        checked={item.is_selected}
                        onChange={() => handleToggleItem(item)}
                        disabled={isItemUpdating}
                        className="h-4 w-4 rounded-sm border-gray-300 text-emerald-600 focus:ring-emerald-500 mt-1 cursor-pointer shrink-0"
                        title={item.is_selected ? "Exclude from plan" : "Include in plan"}
                      />

                      <div className="relative h-16 w-16 sm:h-20 sm:w-20 rounded-lg overflow-hidden bg-muted shrink-0 border">
                        <MissionProductImage
                          src={item.image_url}
                          alt={item.product_name}
                          sizes="80px"
                        />
                      </div>

                      <div className="space-y-1 min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-1.5">
                          {item.brand && (
                            <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                              {item.brand}
                            </span>
                          )}
                          <span className="text-[10px] text-muted-foreground/60">•</span>
                          <span className="text-[11px] text-muted-foreground font-mono">
                            SKU: {item.sku}
                          </span>
                        </div>

                        <h4 className="text-xs sm:text-sm font-bold text-foreground truncate">
                          {item.product_name}
                        </h4>

                        <div className="flex flex-wrap items-center gap-2 pt-0.5">
                          <Badge variant="outline" className="text-[10px] bg-muted/30">
                            <Store className="h-3 w-3 mr-1 text-emerald-600" />
                            {item.retailer_name}
                          </Badge>

                          {item.is_in_stock ? (
                            <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-medium">
                              In Stock ({item.available_stock} available)
                            </span>
                          ) : (
                            <span className="text-[11px] text-destructive font-medium">
                              Out of Stock
                            </span>
                          )}

                          {item.price_changed && (
                            <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 text-[10px]">
                              Price Updated
                            </Badge>
                          )}
                        </div>

                        {item.recommendation_reason && (
                          <p className="text-[11px] text-muted-foreground/90 italic pt-0.5 line-clamp-1">
                            &quot;{item.recommendation_reason}&quot;
                          </p>
                        )}
                      </div>
                    </div>

                    {/* Right: Quantity Stepper + Price + Actions */}
                    <div className="flex items-center justify-between sm:justify-end gap-4 w-full sm:w-auto pt-2 sm:pt-0 border-t sm:border-t-0 border-muted/60 shrink-0">
                      {/* Quantity Stepper */}
                      <div className="flex items-center border rounded-lg bg-background">
                        <button
                          type="button"
                          onClick={() => handleQuantityChange(item, item.quantity - 1)}
                          disabled={item.quantity <= 1 || isItemUpdating}
                          className="p-1.5 hover:bg-muted text-muted-foreground hover:text-foreground disabled:opacity-40 transition-colors"
                        >
                          <Minus className="h-3.5 w-3.5" />
                        </button>
                        <span className="px-2.5 text-xs font-bold font-mono">
                          {item.quantity}
                        </span>
                        <button
                          type="button"
                          onClick={() => handleQuantityChange(item, item.quantity + 1)}
                          disabled={item.quantity >= item.available_stock || isItemUpdating}
                          className="p-1.5 hover:bg-muted text-muted-foreground hover:text-foreground disabled:opacity-40 transition-colors"
                        >
                          <Plus className="h-3.5 w-3.5" />
                        </button>
                      </div>

                      {/* Pricing */}
                      <div className="text-right min-w-[80px]">
                        <div className="text-xs sm:text-sm font-extrabold text-foreground">
                          {formatPrice(item.subtotal_paise)}
                        </div>
                        <div className="text-[10px] text-muted-foreground">
                          {formatPrice(item.current_selling_price_paise)} each
                        </div>
                      </div>

                      {/* Alternative & Delete Actions */}
                      <div className="flex items-center gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openAlternativesModal(item)}
                          disabled={isItemUpdating}
                          title="View similar alternative products"
                          className="h-8 px-2 text-xs text-muted-foreground hover:text-emerald-700"
                        >
                          <RefreshCw className="h-3.5 w-3.5 mr-1" />
                          <span className="hidden md:inline">Alternative</span>
                        </Button>

                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteItem(item)}
                          disabled={isItemUpdating}
                          title="Remove item from plan"
                          className="h-8 w-8 p-0 text-muted-foreground hover:text-destructive"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )))}
      </div>

      {/* Alternative Products Modal */}
      {altModalItem && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-card border rounded-2xl max-w-2xl w-full max-h-[85vh] flex flex-col shadow-2xl overflow-hidden animate-in fade-in-0 zoom-in-95">
            <div className="p-4 border-b flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-foreground flex items-center gap-2">
                  <RefreshCw className="h-4 w-4 text-emerald-600" />
                  Select an Alternative
                </h3>
                <p className="text-xs text-muted-foreground">
                  Replace &quot;{altModalItem.product_name}&quot; with a matching product from verified retailers.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setAltModalItem(null)}
                className="p-1 rounded-md text-muted-foreground hover:text-foreground"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="p-4 overflow-y-auto space-y-3 flex-1">
              {loadingAlts ? (
                <div className="p-10 text-center text-xs text-muted-foreground flex items-center justify-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin text-emerald-600" />
                  Finding in-stock alternatives...
                </div>
              ) : alternatives.length === 0 ? (
                <div className="p-8 text-center text-xs text-muted-foreground space-y-2 border border-dashed rounded-xl">
                  <Info className="h-6 w-6 mx-auto text-muted-foreground/60" />
                  <p className="font-semibold text-foreground">No direct alternatives found</p>
                  <p>All other products in this department are currently out of stock or already in your plan.</p>
                </div>
              ) : (
                alternatives.map((alt) => {
                  const isCheaper = alt.price_diff_paise < 0;
                  const isMoreExpensive = alt.price_diff_paise > 0;
                  const diffFormatted = formatPrice(Math.abs(alt.price_diff_paise));

                  return (
                    <div
                      key={alt.listing_id}
                      className="p-3.5 rounded-xl border bg-background hover:border-emerald-500/50 transition-all flex items-center justify-between gap-4"
                    >
                      <div className="flex items-center gap-3 min-w-0 flex-1">
                        <div className="relative h-14 w-14 rounded-lg overflow-hidden bg-muted shrink-0 border">
                          <MissionProductImage
                            src={alt.image_url}
                            alt={alt.product_name}
                            sizes="56px"
                          />
                        </div>

                        <div className="space-y-0.5 min-w-0">
                          <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                            {alt.brand}
                          </span>
                          <h4 className="text-xs font-bold text-foreground truncate">
                            {alt.product_name}
                          </h4>
                          <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                            <span className="font-medium text-foreground">
                              {formatPrice(alt.selling_price_paise)}
                            </span>
                            <span>•</span>
                            <span className="text-emerald-700 dark:text-emerald-400">
                              {alt.retailer_name}
                            </span>
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-3 shrink-0">
                        <div className="text-right">
                          {isCheaper && (
                            <span className="text-xs font-bold text-emerald-600 block">
                              Save {diffFormatted}
                            </span>
                          )}
                          {isMoreExpensive && (
                            <span className="text-xs font-bold text-amber-600 block">
                              +{diffFormatted}
                            </span>
                          )}
                          {alt.price_diff_paise === 0 && (
                            <span className="text-xs font-bold text-muted-foreground block">
                              Same Price
                            </span>
                          )}
                          <span className="text-[10px] text-muted-foreground">
                            {alt.available_stock} in stock
                          </span>
                        </div>

                        <Button
                          size="sm"
                          disabled={replacingAlt}
                          onClick={() => handleSelectAlternative(alt)}
                          className="bg-brand-yellow hover:bg-brand-yellow-dark text-ink text-xs h-8"
                        >
                          {replacingAlt ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            "Switch"
                          )}
                        </Button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            <div className="p-3 border-t bg-muted/20 flex justify-end">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setAltModalItem(null)}
                className="text-xs"
              >
                Close
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Cart Addition Feedback Modal */}
      {cartSuccessResponse && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-card border rounded-2xl max-w-md w-full p-6 space-y-5 shadow-2xl animate-in fade-in-0 zoom-in-95">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-full bg-emerald-100 dark:bg-emerald-950 flex items-center justify-center text-emerald-600 shrink-0">
                <CheckCircle2 className="h-6 w-6" />
              </div>
              <div>
                <h3 className="text-base font-bold text-foreground">Mission Items Added!</h3>
                <p className="text-xs text-muted-foreground">
                  {cartSuccessResponse.added_items_count} products transferred to your shopping basket.
                </p>
              </div>
            </div>

            {cartSuccessResponse.warnings.length > 0 && (
              <div className="p-3 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-500/20 space-y-1.5 text-xs text-amber-800 dark:text-amber-300">
                <div className="font-semibold flex items-center gap-1.5">
                  <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />
                  Marketplace Updates
                </div>
                <ul className="list-disc pl-4 space-y-0.5 text-[11px]">
                  {cartSuccessResponse.warnings.map((w, idx) => (
                    <li key={idx}>{w}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="flex items-center gap-2.5 pt-2">
              <Link href="/cart" className="flex-1">
                <Button className="w-full bg-brand-yellow hover:bg-brand-yellow-dark text-ink text-xs font-semibold h-10">
                  <ShoppingCart className="h-3.5 w-3.5 mr-1.5" />
                  View Shopping Basket
                </Button>
              </Link>
              <Button
                variant="outline"
                onClick={() => setCartSuccessResponse(null)}
                className="text-xs h-10"
              >
                Stay Here
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {confirmDeleteOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-card border rounded-2xl max-w-sm w-full p-6 space-y-4 shadow-2xl">
            <div className="space-y-1">
              <h3 className="text-base font-bold text-foreground">Delete Shopping Mission?</h3>
              <p className="text-xs text-muted-foreground">
                This will permanently delete &quot;{mission.title}&quot; and its customized plan. This action cannot be undone.
              </p>
            </div>
            <div className="flex items-center justify-end gap-2 pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setConfirmDeleteOpen(false)}
                disabled={isDeleting}
                className="text-xs"
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={handleDeleteMission}
                disabled={isDeleting}
                className="text-xs"
              >
                {isDeleting ? "Deleting..." : "Delete Plan"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
