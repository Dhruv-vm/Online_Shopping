"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { apiClient } from "@/lib/api/client";
import { formatPrice } from "@/lib/utils";
import type { ProductDetail, ProductVariantDetail } from "@/types";
import {
  ArrowLeft,
  CheckCircle2,
  ChevronRight,
  Info,
  Loader2,
  PackageX,
  Scale,
  ShieldCheck,
  ShoppingBag,
  ShoppingBasket,
  Sparkles,
  Star,
  Store,
  Tag,
  Truck,
} from "lucide-react";
import { useCart } from "@/lib/cart/cart-context";
import { useCompare } from "@/lib/compare/compare-context";

interface ProductPageProps {
  params: Promise<{ id: string }>;
}

export default function ProductDetailPage({ params }: ProductPageProps) {
  const resolvedParams = use(params);
  const productIdOrSlug = resolvedParams.id;
  const { addItem } = useCart();
  const { isInCompare, toggleCompare } = useCompare();

  const [product, setProduct] = useState<ProductDetail | null>(null);
  const [selectedVariant, setSelectedVariant] = useState<ProductVariantDetail | null>(null);
  const [selectedListingId, setSelectedListingId] = useState<string | null>(null);
  const [selectedImageIndex, setSelectedImageIndex] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [quantity, setQuantity] = useState(1);
  const [isAdding, setIsAdding] = useState(false);
  const [addSuccess, setAddSuccess] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const [activeAddingListingId, setActiveAddingListingId] = useState<string | null>(null);

  const handleAddToCart = async (listingId: string, qty = 1) => {
    setIsAdding(true);
    setActiveAddingListingId(listingId);
    setAddError(null);
    setAddSuccess(false);
    try {
      await addItem(listingId, qty);
      setAddSuccess(true);
      setTimeout(() => setAddSuccess(false), 4000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to add to basket";
      setAddError(msg);
    } finally {
      setIsAdding(false);
      setActiveAddingListingId(null);
    }
  };

  useEffect(() => {
    async function fetchDetail() {
      setIsLoading(true);
      setError(null);
      try {
        const data = await apiClient.getProduct(productIdOrSlug);
        setProduct(data);
        if (data.variants && data.variants.length > 0) {
          setSelectedVariant(data.variants[0]);
        }
      } catch (err) {
        console.error("Error loading product detail:", err);
        setError("Product not found or service unavailable.");
      } finally {
        setIsLoading(false);
      }
    }
    fetchDetail();
  }, [productIdOrSlug]);

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-24 flex flex-col items-center justify-center space-y-4">
        <Loader2 className="h-10 w-10 animate-spin text-emerald-600" />
        <p className="text-sm text-muted-foreground font-medium">
          Retrieving live product details from PostgreSQL...
        </p>
      </div>
    );
  }

  if (error || !product) {
    return (
      <div className="container mx-auto px-4 py-20 max-w-lg text-center space-y-5">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-destructive/10 text-destructive">
          <PackageX className="h-7 w-7" />
        </div>
        <div className="space-y-1">
          <h2 className="text-2xl font-bold text-foreground">Product Not Found</h2>
          <p className="text-sm text-muted-foreground">
            {error || "The requested item could not be retrieved from the catalogue."}
          </p>
        </div>
        <Link href="/products">
          <Button variant="outline" className="mt-2">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Catalogue
          </Button>
        </Link>
      </div>
    );
  }

  // Active listings for the selected variant
  const activeListings = selectedVariant ? selectedVariant.listings : [];
  const currentListing =
    activeListings.find((l) => l.id === selectedListingId) ||
    (activeListings.length > 0 ? activeListings[0] : null);

  const currentDisplayImage =
    product.images[selectedImageIndex]?.url ||
    product.images[0]?.url ||
    "";

  const discountPercent =
    currentListing &&
    currentListing.original_price_paise > currentListing.selling_price_paise
      ? Math.round(
          ((currentListing.original_price_paise -
            currentListing.selling_price_paise) /
            currentListing.original_price_paise) *
            100
        )
      : 0;

  return (
    <div className="container mx-auto px-4 py-8 sm:px-6 space-y-8">
      {/* Breadcrumb Navigation */}
      <nav className="flex items-center space-x-2 text-xs text-muted-foreground">
        <Link href="/" className="hover:text-foreground">Home</Link>
        <ChevronRight className="h-3.5 w-3.5" />
        <Link href="/products" className="hover:text-foreground">Catalogue</Link>
        <ChevronRight className="h-3.5 w-3.5" />
        <Link
          href={`/products?category_slug=${product.category_slug}`}
          className="hover:text-foreground capitalize"
        >
          {product.category_name}
        </Link>
        <ChevronRight className="h-3.5 w-3.5" />
        <span className="truncate max-w-[200px] text-foreground font-medium">
          {product.name}
        </span>
      </nav>

      {/* Main Product Showcase Section */}
      <div className="grid grid-cols-1 gap-10 lg:grid-cols-2">
        {/* Left Column: Gallery */}
        <div className="space-y-4">
          <div className="relative aspect-square w-full overflow-hidden rounded-2xl border bg-muted/20">
            {currentDisplayImage ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={currentDisplayImage}
                alt={product.name}
                className="h-full w-full object-cover object-center"
              />
            ) : (
              <div className="flex h-full w-full items-center justify-center text-muted-foreground">
                <Tag className="h-16 w-16 stroke-1" />
              </div>
            )}

            {discountPercent > 0 && (
              <Badge className="absolute top-4 left-4 bg-rose-600 text-white font-bold text-xs shadow-md">
                {discountPercent}% OFF
              </Badge>
            )}

            <div className="absolute top-4 right-4">
              <Badge
                variant={product.is_in_stock ? "secondary" : "outline"}
                className={
                  product.is_in_stock
                    ? "bg-emerald-600/10 text-emerald-700 dark:text-emerald-400 border-emerald-600/30"
                    : "text-destructive border-destructive/40"
                }
              >
                {product.is_in_stock ? "In Stock" : "Currently Unavailable"}
              </Badge>
            </div>
          </div>

          {/* Gallery Thumbnails */}
          {product.images.length > 1 && (
            <div className="flex items-center gap-3 overflow-x-auto pb-2">
              {product.images.map((img, idx) => (
                <button
                  key={img.id}
                  type="button"
                  onClick={() => setSelectedImageIndex(idx)}
                  className={`relative h-20 w-20 shrink-0 overflow-hidden rounded-xl border-2 transition-all ${
                    selectedImageIndex === idx
                      ? "border-emerald-600 ring-2 ring-emerald-600/20"
                      : "border-border hover:border-muted-foreground"
                  }`}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={img.url}
                    alt={img.alt_text || `Thumbnail ${idx + 1}`}
                    className="h-full w-full object-cover object-center"
                  />
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Right Column: Details & Variant Selection */}
        <div className="space-y-6">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-widest text-emerald-700 dark:text-emerald-400">
                {product.brand}
              </span>
              <span className="text-muted-foreground text-xs">•</span>
              <span className="text-xs text-muted-foreground">
                SKU: {selectedVariant?.sku || "N/A"}
              </span>
            </div>
            <h1 className="text-2xl font-extrabold tracking-tight text-foreground sm:text-3xl">
              {product.name}
            </h1>
          </div>

          {/* Pricing & Key Summary */}
          {currentListing ? (
            <div className="space-y-4">
              <div className="flex flex-col gap-2 p-4 rounded-xl bg-muted/40 border">
                <div className="flex items-baseline gap-3">
                  <div>
                    <span className="text-3xl font-extrabold text-foreground">
                      {formatPrice(currentListing.selling_price_paise, currentListing.currency)}
                    </span>
                    {currentListing.original_price_paise > currentListing.selling_price_paise && (
                      <span className="text-sm text-muted-foreground line-through ml-2.5">
                        {formatPrice(currentListing.original_price_paise, currentListing.currency)}
                      </span>
                    )}
                  </div>
                  {discountPercent > 0 && (
                    <Badge variant="outline" className="text-emerald-700 border-emerald-600/40 text-xs font-semibold">
                      Save {formatPrice(currentListing.original_price_paise - currentListing.selling_price_paise, currentListing.currency)}
                    </Badge>
                  )}
                </div>

                {/* Selected Seller Metadata */}
                <div className="flex items-center gap-2 text-xs text-muted-foreground pt-1 border-t border-border/50">
                  <span className="text-foreground font-semibold flex items-center gap-1">
                    <Store className="h-3.5 w-3.5 text-emerald-600" />
                    Sold by {currentListing.retailer_name}
                  </span>
                  <span>•</span>
                  <span className="flex items-center gap-0.5 text-amber-600 dark:text-amber-400 font-medium">
                    <Star className="h-3 w-3 fill-amber-500" />
                    {currentListing.retailer_rating.toFixed(1)}
                  </span>
                  {currentListing.retailer_state && (
                    <>
                      <span>•</span>
                      <span>Ships from {currentListing.retailer_state}</span>
                    </>
                  )}
                  <span>•</span>
                  <span className="text-emerald-700 dark:text-emerald-400 font-medium">
                    {currentListing.available_quantity} units available
                  </span>
                </div>
              </div>

              {/* Multi-Seller Offer Selector */}
              {activeListings.length > 1 && (
                <div className="space-y-2 rounded-xl border p-3.5 bg-card">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-bold text-foreground flex items-center gap-1.5">
                      <Store className="h-3.5 w-3.5 text-emerald-600" />
                      Select Seller Offer ({activeListings.length} retailers available):
                    </span>
                    <span className="text-[11px] text-muted-foreground">Compare offers</span>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {activeListings.map((listing, idx) => {
                      const isSelected = currentListing?.id === listing.id;
                      return (
                        <button
                          key={listing.id}
                          type="button"
                          onClick={() => setSelectedListingId(listing.id)}
                          className={`p-2.5 rounded-lg border text-left transition-all flex flex-col justify-between text-xs ${
                            isSelected
                              ? "border-emerald-600 bg-emerald-50/60 dark:bg-emerald-950/40 ring-1 ring-emerald-600"
                              : "border-border hover:border-muted-foreground bg-muted/20"
                          }`}
                        >
                          <div className="flex items-center justify-between gap-1">
                            <span className="font-bold text-foreground truncate">
                              {listing.retailer_name}
                            </span>
                            {idx === 0 && (
                              <Badge className="bg-emerald-600 text-white text-[9px] py-0 px-1 h-3.5">
                                Best Price
                              </Badge>
                            )}
                          </div>
                          <div className="flex items-baseline justify-between mt-1">
                            <span className="font-extrabold text-foreground text-sm">
                              {formatPrice(listing.selling_price_paise, listing.currency)}
                            </span>
                            <span className="text-[10px] text-muted-foreground">
                              ★ {listing.retailer_rating.toFixed(1)} • {listing.available_quantity} in stock
                            </span>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Add to Basket Control */}
              {currentListing.is_in_stock ? (
                <div className="p-4 rounded-xl border bg-card space-y-3 shadow-xs">
                  <div className="flex items-center gap-3">
                    <div className="flex items-center border rounded-lg overflow-hidden bg-background">
                      <button
                        type="button"
                        onClick={() => setQuantity((q) => Math.max(1, q - 1))}
                        disabled={quantity <= 1 || isAdding}
                        aria-label="Decrease quantity"
                        className="px-3 py-2 hover:bg-muted text-sm font-bold disabled:opacity-40"
                      >
                        -
                      </button>
                      <span className="px-3 py-2 text-sm font-semibold min-w-8 text-center">
                        {quantity}
                      </span>
                      <button
                        type="button"
                        onClick={() =>
                          setQuantity((q) =>
                            Math.min(
                              Math.min(10, currentListing.available_quantity),
                              q + 1
                            )
                          )
                        }
                        disabled={
                          quantity >=
                            Math.min(10, currentListing.available_quantity) ||
                          isAdding
                        }
                        aria-label="Increase quantity"
                        className="px-3 py-2 hover:bg-muted text-sm font-bold disabled:opacity-40"
                      >
                        +
                      </button>
                    </div>

                    <Button
                      onClick={() => handleAddToCart(currentListing.id, quantity)}
                      disabled={isAdding}
                      className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold h-11 shadow-xs text-sm"
                    >
                      {isAdding && activeAddingListingId === currentListing.id ? (
                        <>
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          Adding to Basket...
                        </>
                      ) : (
                        <>
                          <ShoppingBasket className="h-4 w-4 mr-2" />
                          Add to Basket • {formatPrice(currentListing.selling_price_paise * quantity, currentListing.currency)}
                        </>
                      )}
                    </Button>

                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => toggleCompare(product.slug)}
                      className={`h-11 px-4 border ${
                        isInCompare(product.slug)
                          ? "bg-emerald-50 text-emerald-700 border-emerald-600 dark:bg-emerald-950/40 font-semibold"
                          : "hover:bg-muted"
                      }`}
                      title={isInCompare(product.slug) ? "Remove from comparison" : "Add to comparison"}
                    >
                      <Scale className="h-4 w-4 mr-2" />
                      {isInCompare(product.slug) ? "Comparing" : "Compare"}
                    </Button>
                  </div>

                  {addSuccess && (
                    <div className="flex items-center justify-between text-xs text-emerald-700 bg-emerald-50 dark:bg-emerald-950/40 p-2.5 rounded-lg border border-emerald-600/30">
                      <span className="flex items-center gap-1.5 font-medium">
                        <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
                        Added {quantity} unit(s) from {currentListing.retailer_name} to your basket!
                      </span>
                      <Link href="/cart" className="font-bold underline hover:text-emerald-800 shrink-0">
                        View Cart →
                      </Link>
                    </div>
                  )}

                  {addError && (
                    <div className="text-xs text-red-600 bg-red-50 dark:bg-red-950/40 p-2.5 rounded-lg border border-red-600/30">
                      {addError}
                    </div>
                  )}
                </div>
              ) : (
                <Button disabled className="w-full bg-muted text-muted-foreground h-11">
                  Out of Stock from this Seller
                </Button>
              )}
            </div>
          ) : (
            <div className="p-4 rounded-xl bg-muted/40 border text-sm text-muted-foreground">
              No active retail listings available for this variant.
            </div>
          )}

          {/* Variant Picker */}
          {product.variants.length > 0 && (
            <div className="space-y-3 pt-2">
              <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                Select Option / Variant ({product.variants.length})
              </label>
              <div className="flex flex-wrap gap-2.5">
                {product.variants.map((v) => {
                  const isSelected = selectedVariant?.id === v.id;
                  return (
                    <button
                      key={v.id}
                      type="button"
                      onClick={() => setSelectedVariant(v)}
                      className={`flex flex-col items-start px-3.5 py-2 rounded-xl border text-xs font-medium transition-all ${
                        isSelected
                          ? "border-emerald-600 bg-emerald-600/10 text-emerald-950 dark:text-emerald-200 ring-1 ring-emerald-600"
                          : "border-border hover:border-muted-foreground text-foreground"
                      }`}
                    >
                      <span className="font-semibold">{v.name}</span>
                      {v.min_price_paise && (
                        <span className="text-[11px] text-muted-foreground mt-0.5">
                          from {formatPrice(v.min_price_paise)}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Retailer Comparison Section */}
          <div className="space-y-3 pt-4 border-t">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-foreground flex items-center gap-1.5">
                <Store className="h-4 w-4 text-emerald-600" />
                Available from {activeListings.length} {activeListings.length === 1 ? "Retailer" : "Retailers"}
              </h3>
              <span className="text-xs text-muted-foreground">
                Authoritative Real-Time Inventory
              </span>
            </div>

            <div className="space-y-2.5">
              {activeListings.map((listing, index) => {
                const isSelected = currentListing?.id === listing.id;
                return (
                  <Card
                    key={listing.id}
                    className={`overflow-hidden border transition-all ${
                      isSelected
                        ? "border-emerald-600 bg-emerald-600/10 shadow-xs ring-1 ring-emerald-600/50"
                        : index === 0
                        ? "border-emerald-600/50 bg-emerald-600/5 shadow-xs"
                        : "border-border bg-card"
                    }`}
                  >
                    <CardContent className="p-3.5 flex items-center justify-between gap-4">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-sm text-foreground">
                            {listing.retailer_name}
                          </span>
                          {index === 0 && (
                            <Badge className="bg-emerald-600 text-white text-[10px] py-0 px-1.5 h-4">
                              Best Offer
                            </Badge>
                          )}
                          {isSelected && (
                            <Badge variant="outline" className="text-emerald-700 border-emerald-600/40 text-[10px] py-0 px-1.5 h-4">
                              Selected
                            </Badge>
                          )}
                          <span className="flex items-center gap-0.5 text-xs text-amber-600 dark:text-amber-400 font-semibold">
                            <Star className="h-3 w-3 fill-amber-500" />
                            {listing.retailer_rating.toFixed(1)}
                          </span>
                        </div>
                        <div className="flex items-center gap-3 text-xs text-muted-foreground">
                          <span className="flex items-center gap-1 text-emerald-700 dark:text-emerald-400">
                            <CheckCircle2 className="h-3 w-3" />
                            {listing.available_quantity} available in stock
                          </span>
                          {listing.retailer_state && (
                            <>
                              <span>•</span>
                              <span>Location: {listing.retailer_state}</span>
                            </>
                          )}
                          <span>•</span>
                          <span className="font-mono text-[11px]">
                            Ref: {listing.seller_sku}
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center gap-3 text-right">
                        <div>
                          <div className="text-base font-extrabold text-foreground">
                            {formatPrice(listing.selling_price_paise, listing.currency)}
                          </div>
                          {listing.original_price_paise > listing.selling_price_paise && (
                            <div className="text-[11px] text-muted-foreground line-through">
                              {formatPrice(listing.original_price_paise, listing.currency)}
                            </div>
                          )}
                        </div>

                        <div className="flex items-center gap-1.5">
                          {!isSelected && (
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => setSelectedListingId(listing.id)}
                              className="h-8 px-2 text-xs font-semibold text-muted-foreground hover:text-foreground"
                            >
                              Select
                            </Button>
                          )}
                          <Button
                            size="sm"
                            variant={isSelected || index === 0 ? "default" : "outline"}
                            disabled={isAdding || listing.available_quantity <= 0}
                            onClick={() => handleAddToCart(listing.id, 1)}
                            className={`h-8 px-3 text-xs font-semibold ${
                              isSelected || index === 0
                                ? "bg-emerald-600 hover:bg-emerald-700 text-white"
                                : "border-emerald-600/40 text-emerald-700 hover:bg-emerald-50 dark:hover:bg-emerald-950/40"
                            }`}
                          >
                            {isAdding && activeAddingListingId === listing.id ? (
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              "Add"
                            )}
                          </Button>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          </div>

          {/* Commerce Roadmap Callout */}
          <div className="rounded-xl border border-dashed border-emerald-600/30 bg-emerald-600/5 p-4 flex gap-3 text-xs text-emerald-950 dark:text-emerald-200">
            <Info className="h-5 w-5 text-emerald-600 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <span className="font-bold">Phase 2 Universal Shopping Basket</span>
              <p className="text-muted-foreground">
                Multi-retailer persistent cart is live. Add items across diverse sellers, variants, and categories in a single unified basket.
              </p>
            </div>
          </div>

          {/* Product Description */}
          {product.description && (
            <div className="space-y-2 pt-4 border-t text-sm">
              <h4 className="font-bold text-foreground">About this product</h4>
              <p className="text-muted-foreground leading-relaxed">
                {product.description}
              </p>
            </div>
          )}

          {/* Value props */}
          <div className="grid grid-cols-2 gap-3 pt-2 text-xs text-muted-foreground">
            <div className="flex items-center gap-2 p-2.5 rounded-lg border bg-muted/20">
              <Truck className="h-4 w-4 text-emerald-600" />
              <span>Pan-India verified delivery</span>
            </div>
            <div className="flex items-center gap-2 p-2.5 rounded-lg border bg-muted/20">
              <ShieldCheck className="h-4 w-4 text-emerald-600" />
              <span>100% Genuine brand guarantee</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
