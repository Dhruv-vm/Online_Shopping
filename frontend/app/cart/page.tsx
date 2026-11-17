"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  ChevronRight,
  Info,
  Loader2,
  Minus,
  Plus,
  ShoppingBasket,
  Store,
  Trash2,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useCart } from "@/lib/cart/cart-context";
import { formatPrice } from "@/lib/utils";
import type { CartItem } from "@/types";

export default function CartPage() {
  const {
    cart,
    items,
    itemCount,
    totalQuantity,
    subtotalPaise,
    isLoading,
    isMutating,
    error,
    warnings,
    updateQuantity,
    removeItem,
    clearCart,
  } = useCart();

  const [activeItemId, setActiveItemId] = useState<string | null>(null);
  const [clearing, setClearing] = useState(false);

  const handleQuantityChange = async (itemId: string, newQty: number) => {
    if (newQty < 1 || newQty > 10) return;
    setActiveItemId(itemId);
    try {
      await updateQuantity(itemId, newQty);
    } catch {
      // Error handled in cart context
    } finally {
      setActiveItemId(null);
    }
  };

  const handleRemove = async (itemId: string) => {
    setActiveItemId(itemId);
    try {
      await removeItem(itemId);
    } catch {
      // Error handled in cart context
    } finally {
      setActiveItemId(null);
    }
  };

  const handleClear = async () => {
    if (!window.confirm("Are you sure you want to clear your shopping cart?")) {
      return;
    }
    setClearing(true);
    try {
      await clearCart();
    } finally {
      setClearing(false);
    }
  };

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-24 flex flex-col items-center justify-center space-y-4">
        <Loader2 className="h-10 w-10 animate-spin text-emerald-600" />
        <p className="text-sm text-muted-foreground font-medium">
          Loading your universal basket...
        </p>
      </div>
    );
  }

  // Empty state
  if (!items || items.length === 0) {
    return (
      <div className="container mx-auto px-4 py-20 max-w-xl text-center space-y-6">
        <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-3xl bg-emerald-600/10 text-emerald-700 dark:text-emerald-400">
          <ShoppingBasket className="h-10 w-10" />
        </div>
        <div className="space-y-2">
          <h1 className="text-2xl sm:text-3xl font-extrabold text-foreground tracking-tight">
            Your Basket is Empty
          </h1>
          <p className="text-sm text-muted-foreground max-w-md mx-auto">
            You haven&apos;t added any items to your shopping cart yet. Explore
            products across multiple retailers and verified brands.
          </p>
        </div>
        <div>
          <Link href="/products">
            <Button className="bg-emerald-600 hover:bg-emerald-700 text-white font-semibold px-6 h-11 shadow-sm">
              Explore Products
              <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  // Group items by retailer for multi-retailer visibility
  const itemsByRetailer = items.reduce<Record<string, CartItem[]>>((acc, item) => {
    const key = item.retailer_name;
    if (!acc[key]) acc[key] = [];
    acc[key].push(item);
    return acc;
  }, {});

  return (
    <div className="container mx-auto px-4 py-8 max-w-6xl space-y-6">
      {/* Breadcrumb & Header */}
      <div className="space-y-1">
        <div className="flex items-center text-xs text-muted-foreground gap-1.5">
          <Link href="/" className="hover:text-foreground">
            Home
          </Link>
          <ChevronRight className="h-3.5 w-3.5" />
          <span className="text-foreground font-medium">Shopping Cart</span>
        </div>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pt-1">
          <div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground flex items-center gap-2.5">
              Shopping Basket
              <Badge
                variant="outline"
                className="text-emerald-700 border-emerald-600/40 text-xs py-0.5"
              >
                {totalQuantity} {totalQuantity === 1 ? "item" : "items"}
              </Badge>
            </h1>
            <p className="text-xs text-muted-foreground mt-0.5">
              Items from {cart?.retailers.length || 1} distinct{" "}
              {cart?.retailers.length === 1 ? "retailer" : "retailers"} in one
              unified cart.
            </p>
          </div>

          <Button
            variant="ghost"
            size="sm"
            onClick={handleClear}
            disabled={isMutating || clearing}
            className="text-xs text-muted-foreground hover:text-red-600 self-start sm:self-auto"
          >
            <Trash2 className="h-3.5 w-3.5 mr-1.5" />
            Clear Basket
          </Button>
        </div>
      </div>

      {/* Cart Warnings / Alerts */}
      {warnings && warnings.length > 0 && (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 space-y-2 text-xs text-amber-900 dark:text-amber-200">
          <div className="flex items-center gap-2 font-bold text-amber-800 dark:text-amber-300">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>Important Cart Notices ({warnings.length})</span>
          </div>
          <ul className="list-disc list-inside space-y-1 pl-1">
            {warnings.map((warn, i) => (
              <li key={i}>{warn}</li>
            ))}
          </ul>
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3.5 flex items-center gap-2 text-xs text-red-700 dark:text-red-300">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Main Grid: Left Items List, Right Order Summary */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Cart Items Grouped by Retailer */}
        <div className="lg:col-span-8 space-y-6">
          {Object.entries(itemsByRetailer).map(([retailerName, retailerItems]) => (
            <Card key={retailerName} className="border shadow-xs overflow-hidden">
              <CardHeader className="bg-muted/40 py-3 px-4 border-b flex flex-row items-center justify-between space-y-0">
                <div className="flex items-center gap-2">
                  <Store className="h-4 w-4 text-emerald-600" />
                  <span className="font-bold text-sm text-foreground">
                    Seller: {retailerName}
                  </span>
                </div>
                <Badge variant="secondary" className="text-[11px] font-medium">
                  {retailerItems.length}{" "}
                  {retailerItems.length === 1 ? "product" : "products"}
                </Badge>
              </CardHeader>

              <CardContent className="p-0 divide-y">
                {retailerItems.map((item) => {
                  const isBusy = isMutating && activeItemId === item.id;
                  return (
                    <div
                      key={item.id}
                      className="p-4 sm:p-5 flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between"
                    >
                      {/* Product Thumbnail & Details */}
                      <div className="flex items-start gap-4 flex-1">
                        <div className="h-20 w-20 shrink-0 rounded-xl bg-muted/60 border overflow-hidden flex items-center justify-center">
                          {item.primary_image_url ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img
                              src={item.primary_image_url}
                              alt={item.product_name}
                              className="h-full w-full object-cover object-center"
                            />
                          ) : (
                            <ShoppingBasket className="h-8 w-8 text-muted-foreground/40" />
                          )}
                        </div>

                        <div className="space-y-1">
                          <Link
                            href={`/products/${item.product_slug || item.product_id}`}
                            className="font-bold text-sm text-foreground hover:text-emerald-700 transition-colors line-clamp-1"
                          >
                            {item.product_name}
                          </Link>

                          {item.variant_name && (
                            <div className="text-xs text-muted-foreground">
                              Variant:{" "}
                              <span className="font-medium text-foreground">
                                {item.variant_name}
                              </span>
                            </div>
                          )}

                          {item.attributes &&
                            Object.keys(item.attributes).length > 0 && (
                              <div className="flex flex-wrap gap-1 text-[11px] text-muted-foreground">
                                {Object.entries(item.attributes).map(
                                  ([k, v]) => (
                                    <span
                                      key={k}
                                      className="inline-block bg-muted px-1.5 py-0.5 rounded"
                                    >
                                      {k}: {String(v)}
                                    </span>
                                  )
                                )}
                              </div>
                            )}

                          {/* Availability / Stock Notice */}
                          {!item.is_available && (
                            <div className="flex items-center gap-1 text-xs text-red-600 font-semibold pt-0.5">
                              <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                              {item.validation_message || "Item unavailable"}
                            </div>
                          )}
                          {item.is_available && item.available_stock <= 5 && (
                            <div className="text-[11px] text-amber-600 dark:text-amber-400 font-medium pt-0.5">
                              Only {item.available_stock} units left in stock
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Quantity Controls & Line Subtotal */}
                      <div className="flex sm:flex-col items-center sm:items-end justify-between w-full sm:w-auto gap-3 pt-2 sm:pt-0 border-t sm:border-0">
                        {/* Unit & Subtotal Price */}
                        <div className="text-left sm:text-right">
                          <div className="text-base font-extrabold text-foreground">
                            {formatPrice(item.subtotal_paise)}
                          </div>
                          <div className="text-[11px] text-muted-foreground">
                            {formatPrice(item.unit_price_paise)} each
                          </div>
                        </div>

                        {/* Controls */}
                        <div className="flex items-center gap-2">
                          <div className="flex items-center border rounded-lg bg-background overflow-hidden h-8">
                            <button
                              type="button"
                              onClick={() =>
                                handleQuantityChange(item.id, item.quantity - 1)
                              }
                              disabled={item.quantity <= 1 || isBusy}
                              aria-label="Decrease quantity"
                              className="px-2.5 h-full hover:bg-muted font-bold disabled:opacity-40 transition-colors"
                            >
                              <Minus className="h-3 w-3" />
                            </button>
                            <span className="px-2 text-xs font-semibold min-w-6 text-center">
                              {isBusy ? (
                                <Loader2 className="h-3 w-3 animate-spin mx-auto" />
                              ) : (
                                item.quantity
                              )}
                            </span>
                            <button
                              type="button"
                              onClick={() =>
                                handleQuantityChange(item.id, item.quantity + 1)
                              }
                              disabled={
                                item.quantity >= 10 ||
                                item.quantity >= item.available_stock ||
                                isBusy
                              }
                              aria-label="Increase quantity"
                              className="px-2.5 h-full hover:bg-muted font-bold disabled:opacity-40 transition-colors"
                            >
                              <Plus className="h-3 w-3" />
                            </button>
                          </div>

                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleRemove(item.id)}
                            disabled={isBusy}
                            title="Remove item"
                            aria-label={`Remove ${item.product_name}`}
                            className="h-8 w-8 p-0 text-muted-foreground hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/40"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Right Column: Order Summary & Retailer Breakdown */}
        <div className="lg:col-span-4 space-y-4">
          <Card className="border shadow-xs">
            <CardHeader className="pb-3 border-b bg-muted/20">
              <CardTitle className="text-base font-bold">
                Order Summary
              </CardTitle>
            </CardHeader>
            <CardContent className="p-5 space-y-4">
              {/* Line item tallies */}
              <div className="space-y-2 text-xs text-muted-foreground">
                <div className="flex justify-between">
                  <span>Distinct Items ({itemCount})</span>
                  <span className="font-medium text-foreground">
                    {totalQuantity} units
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Catalogue Subtotal</span>
                  <span className="font-semibold text-foreground">
                    {formatPrice(subtotalPaise)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Delivery & Handling</span>
                  <span className="text-emerald-700 dark:text-emerald-400 font-medium">
                    Calculated at Checkout
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Taxes (GST)</span>
                  <span className="text-muted-foreground">
                    Calculated at Checkout
                  </span>
                </div>
              </div>

              {/* Retailer Breakdown Summary */}
              {cart && cart.retailers && cart.retailers.length > 0 && (
                <div className="pt-3 border-t space-y-2">
                  <div className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                    Multi-Seller Subtotals
                  </div>
                  <div className="space-y-1.5">
                    {cart.retailers.map((ret) => (
                      <div
                        key={ret.retailer_id}
                        className="flex justify-between text-xs items-center bg-muted/40 p-2 rounded-lg"
                      >
                        <span className="truncate max-w-[160px] font-medium text-foreground">
                          {ret.retailer_name}
                        </span>
                        <div className="text-right">
                          <span className="font-semibold text-foreground">
                            {formatPrice(ret.subtotal_paise)}
                          </span>
                          <span className="text-[10px] text-muted-foreground block">
                            {ret.item_count} {ret.item_count === 1 ? "item" : "items"}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Grand Subtotal */}
              <div className="pt-3 border-t flex justify-between items-baseline">
                <span className="text-sm font-bold text-foreground">
                  Estimated Total
                </span>
                <span className="text-2xl font-extrabold text-foreground">
                  {formatPrice(subtotalPaise)}
                </span>
              </div>

              {/* Proceed to Checkout CTA */}
              <div className="space-y-2 pt-2">
                <Button
                  className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-semibold h-11 text-sm shadow-sm"
                  disabled={items.some((i) => !i.is_available)}
                  title={
                    items.some((i) => !i.is_available)
                      ? "Resolve unavailable items to proceed"
                      : "Proceed to Checkout (Phase 2C)"
                  }
                  onClick={() =>
                    alert(
                      "Phase 2B Universal Cart is complete! Checkout state machine and payment integration will activate in Phase 2C."
                    )
                  }
                >
                  Proceed to Checkout
                  <ArrowRight className="h-4 w-4 ml-2" />
                </Button>

                {items.some((i) => !i.is_available) && (
                  <p className="text-[11px] text-center text-red-600">
                    Please remove or update unavailable items before checkout.
                  </p>
                )}
              </div>

              {/* Security & Authenticity guarantees */}
              <div className="pt-3 border-t space-y-1 text-[11px] text-muted-foreground">
                <div className="flex items-center gap-1.5 text-emerald-700 dark:text-emerald-400 font-medium">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  <span>Server-authoritative live prices & stock</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <Info className="h-3.5 w-3.5 text-muted-foreground" />
                  <span>Single unified cart across all verified sellers</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
