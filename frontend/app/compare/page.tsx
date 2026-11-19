"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { apiClient } from "@/lib/api/client";
import { useCart } from "@/lib/cart/cart-context";
import { useCompare } from "@/lib/compare/compare-context";
import { formatPrice } from "@/lib/utils";
import type { ProductDetail, ProductListingDetail } from "@/types";
import {
  ArrowRight,
  CheckCircle2,
  ExternalLink,
  Layers,
  Loader2,
  Scale,
  ShoppingBasket,
  Star,
  Store,
  Tag,
  Trash2,
  X,
} from "lucide-react";

export default function ComparePage() {
  const { compareSlugs, removeFromCompare, clearCompare } = useCompare();
  const { addItem } = useCart();

  const [products, setProducts] = useState<ProductDetail[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [addingListingId, setAddingListingId] = useState<string | null>(null);
  const [addedListingId, setAddedListingId] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    async function loadProducts() {
      if (compareSlugs.length === 0) {
        setProducts([]);
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      try {
        const results = await Promise.allSettled(
          compareSlugs.map((slug) => apiClient.getProduct(slug))
        );

        if (mounted) {
          const loaded: ProductDetail[] = [];
          results.forEach((res) => {
            if (res.status === "fulfilled" && res.value) {
              loaded.push(res.value);
            }
          });
          setProducts(loaded);
        }
      } catch (err) {
        console.error("Failed to load products for comparison:", err);
      } finally {
        if (mounted) {
          setIsLoading(false);
        }
      }
    }

    loadProducts();

    return () => {
      mounted = false;
    };
  }, [compareSlugs]);

  const handleAddToCart = async (listing: ProductListingDetail) => {
    try {
      setAddingListingId(listing.id);
      await addItem(listing.id, 1);
      setAddedListingId(listing.id);
      setTimeout(() => setAddedListingId(null), 3000);
    } catch (err) {
      console.error("Failed to add to basket:", err);
    } finally {
      setAddingListingId(null);
    }
  };

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-24 flex flex-col items-center justify-center space-y-4">
        <Loader2 className="h-10 w-10 animate-spin text-emerald-600" />
        <p className="text-sm text-muted-foreground font-medium">
          Loading comparison data...
        </p>
      </div>
    );
  }

  if (products.length === 0) {
    return (
      <div className="container mx-auto px-4 py-16 max-w-2xl text-center">
        <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-2xl bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 border border-emerald-600/20 shadow-sm">
          <Scale className="h-10 w-10" />
        </div>
        <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground">
          No Products Selected For Comparison
        </h1>
        <p className="mt-3 text-muted-foreground text-sm sm:text-base leading-relaxed">
          Select 2 to 4 products across any category while browsing our catalogue to compare prices, specifications, retailers, and stock availability side-by-side.
        </p>
        <div className="mt-8 flex justify-center gap-4">
          <Link href="/products">
            <Button className="bg-emerald-600 hover:bg-emerald-700 text-white font-semibold flex items-center gap-2">
              Browse Catalogue
              <ArrowRight className="h-4 w-4" />
            </Button>
          </Link>
          <Link href="/categories">
            <Button variant="outline">
              View Categories
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  // Gather all unique attribute names across all products
  const attributeKeys = Array.from(
    new Set(
      products.flatMap((p) =>
        p.variants.flatMap((v) => Object.keys(v.attributes || {}))
      )
    )
  );

  return (
    <div className="container mx-auto px-4 py-8 max-w-7xl">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-border">
        <div>
          <div className="flex items-center gap-2">
            <Scale className="h-6 w-6 text-emerald-600" />
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground">
              Product Comparison
            </h1>
            <Badge variant="outline" className="ml-2 font-mono text-xs">
              {products.length} / 4 products
            </Badge>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Side-by-side comparison of pricing, stock, retailers, and technical specifications.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={clearCompare}
            className="text-xs text-destructive hover:bg-destructive/10 hover:text-destructive border-destructive/30"
          >
            <Trash2 className="h-3.5 w-3.5 mr-1.5" />
            Clear Comparison
          </Button>
          {products.length < 4 && (
            <Link href="/products">
              <Button size="sm" variant="secondary" className="text-xs">
                Add More Products
              </Button>
            </Link>
          )}
        </div>
      </div>

      {products.length === 1 && (
        <div className="my-6 p-4 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-600/30 flex flex-col sm:flex-row items-center justify-between gap-3 text-amber-800 dark:text-amber-300 text-sm">
          <div className="flex items-center gap-2">
            <Layers className="h-5 w-5 shrink-0" />
            <span>
              You have selected <strong>1 product</strong>. Add at least one more product to see a side-by-side feature matrix.
            </span>
          </div>
          <Link href="/products">
            <Button size="sm" className="bg-amber-600 hover:bg-amber-700 text-white shrink-0">
              Find Products to Compare
            </Button>
          </Link>
        </div>
      )}

      {/* Comparison Matrix Table */}
      <div className="mt-6 overflow-x-auto rounded-xl border border-border bg-card shadow-xs">
        <table className="w-full border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/40">
              <th className="p-4 font-semibold text-muted-foreground w-48 sm:w-56 shrink-0 align-top">
                Feature / Metric
              </th>
              {products.map((p) => {
                const primaryVariant = p.variants[0];
                const activeListing = primaryVariant?.listings[0];

                return (
                  <th
                    key={p.id}
                    className="p-4 align-top min-w-[260px] max-w-[320px] border-l border-border relative"
                  >
                    <button
                      type="button"
                      onClick={() => removeFromCompare(p.slug)}
                      className="absolute top-3 right-3 p-1 rounded-full text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
                      title="Remove product"
                      aria-label={`Remove ${p.name}`}
                    >
                      <X className="h-4 w-4" />
                    </button>

                    <div className="pr-6 space-y-3">
                      <div className="aspect-square w-full rounded-lg overflow-hidden bg-muted/50 border border-border/60">
                        {p.images && p.images[0]?.url ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            src={p.images[0].url}
                            alt={p.name}
                            className="h-full w-full object-cover object-center"
                          />
                        ) : (
                          <div className="flex h-full w-full items-center justify-center text-muted-foreground">
                            <Tag className="h-10 w-10 stroke-1" />
                          </div>
                        )}
                      </div>

                      <div>
                        <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                          {p.brand}
                        </span>
                        <Link
                          href={`/products/${p.slug}`}
                          className="font-bold text-sm text-foreground hover:text-emerald-700 dark:hover:text-emerald-400 line-clamp-2 mt-0.5 block transition-colors"
                        >
                          {p.name}
                        </Link>
                      </div>

                      {/* Action Button */}
                      {activeListing && activeListing.is_in_stock ? (
                        <Button
                          size="sm"
                          onClick={() => handleAddToCart(activeListing)}
                          disabled={addingListingId === activeListing.id}
                          className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs shadow-xs"
                        >
                          {addingListingId === activeListing.id ? (
                            <>
                              <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                              Adding...
                            </>
                          ) : addedListingId === activeListing.id ? (
                            <>
                              <CheckCircle2 className="h-3.5 w-3.5 mr-1.5" />
                              Added!
                            </>
                          ) : (
                            <>
                              <ShoppingBasket className="h-3.5 w-3.5 mr-1.5" />
                              Add to Basket
                            </>
                          )}
                        </Button>
                      ) : (
                        <Button disabled size="sm" variant="outline" className="w-full text-xs">
                          Out of Stock
                        </Button>
                      )}
                    </div>
                  </th>
                );
              })}
            </tr>
          </thead>

          <tbody className="divide-y divide-border">
            {/* Price Row */}
            <tr className="hover:bg-muted/20">
              <td className="p-4 font-semibold text-foreground bg-muted/20">
                Selling Price
              </td>
              {products.map((p) => {
                const primaryVariant = p.variants[0];
                const activeListing = primaryVariant?.listings[0];
                const price = activeListing?.selling_price_paise ?? p.min_price_paise;
                const originalPrice = activeListing?.original_price_paise ?? p.original_price_paise;

                return (
                  <td key={p.id} className="p-4 border-l border-border align-top">
                    <div className="space-y-1">
                      <div className="text-lg font-extrabold text-foreground">
                        {price > 0 ? formatPrice(price, p.currency) : "Unavailable"}
                      </div>
                      {originalPrice && originalPrice > price && (
                        <div className="text-xs text-muted-foreground line-through">
                          MRP {formatPrice(originalPrice, p.currency)}
                        </div>
                      )}
                    </div>
                  </td>
                );
              })}
            </tr>

            {/* Discount Row */}
            <tr className="hover:bg-muted/20">
              <td className="p-4 font-semibold text-foreground bg-muted/20">
                Discount
              </td>
              {products.map((p) => {
                const primaryVariant = p.variants[0];
                const activeListing = primaryVariant?.listings[0];
                const price = activeListing?.selling_price_paise ?? p.min_price_paise;
                const originalPrice = activeListing?.original_price_paise ?? p.original_price_paise;
                const discount =
                  originalPrice && originalPrice > price
                    ? Math.round(((originalPrice - price) / originalPrice) * 100)
                    : 0;

                return (
                  <td key={p.id} className="p-4 border-l border-border align-top">
                    {discount > 0 ? (
                      <Badge className="bg-rose-600 text-white font-bold text-xs">
                        {discount}% OFF
                      </Badge>
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
                    )}
                  </td>
                );
              })}
            </tr>

            {/* Retailer Row */}
            <tr className="hover:bg-muted/20">
              <td className="p-4 font-semibold text-foreground bg-muted/20">
                Retailer / Seller
              </td>
              {products.map((p) => {
                const primaryVariant = p.variants[0];
                const activeListing = primaryVariant?.listings[0];

                return (
                  <td key={p.id} className="p-4 border-l border-border align-top">
                    {activeListing ? (
                      <div className="space-y-1">
                        <div className="font-semibold text-foreground flex items-center gap-1.5">
                          <Store className="h-4 w-4 text-emerald-600 shrink-0" />
                          {activeListing.retailer_name}
                        </div>
                        <div className="flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400">
                          <Star className="h-3 w-3 fill-amber-500" />
                          <span>{activeListing.retailer_rating.toFixed(1)} Rating</span>
                        </div>
                        {activeListing.retailer_state && (
                          <div className="text-[11px] text-muted-foreground">
                            Ships from {activeListing.retailer_state}
                          </div>
                        )}
                      </div>
                    ) : (
                      <span className="text-xs text-muted-foreground">No active seller</span>
                    )}
                  </td>
                );
              })}
            </tr>

            {/* Stock Availability Row */}
            <tr className="hover:bg-muted/20">
              <td className="p-4 font-semibold text-foreground bg-muted/20">
                Stock Availability
              </td>
              {products.map((p) => {
                const inStock = p.is_in_stock;

                return (
                  <td key={p.id} className="p-4 border-l border-border align-top">
                    {inStock ? (
                      <Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-emerald-600/40 text-xs font-semibold">
                        In Stock ({p.total_available_stock} units)
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="bg-red-50 text-red-700 border-red-600/40 text-xs font-semibold">
                        Out of Stock
                      </Badge>
                    )}
                  </td>
                );
              })}
            </tr>

            {/* Category Row */}
            <tr className="hover:bg-muted/20">
              <td className="p-4 font-semibold text-foreground bg-muted/20">
                Category
              </td>
              {products.map((p) => (
                <td key={p.id} className="p-4 border-l border-border align-top">
                  <Badge variant="secondary" className="text-xs">
                    {p.category_name}
                  </Badge>
                </td>
              ))}
            </tr>

            {/* SKU / Variant Row */}
            <tr className="hover:bg-muted/20">
              <td className="p-4 font-semibold text-foreground bg-muted/20">
                SKU / Options
              </td>
              {products.map((p) => {
                const primaryVariant = p.variants[0];

                return (
                  <td key={p.id} className="p-4 border-l border-border align-top">
                    <div className="font-mono text-xs text-foreground">
                      {primaryVariant?.sku || "—"}
                    </div>
                    <div className="text-[11px] text-muted-foreground mt-0.5">
                      {p.variants.length} variant{p.variants.length === 1 ? "" : "s"} available
                    </div>
                  </td>
                );
              })}
            </tr>

            {/* Description Row */}
            <tr className="hover:bg-muted/20">
              <td className="p-4 font-semibold text-foreground bg-muted/20">
                Overview
              </td>
              {products.map((p) => (
                <td key={p.id} className="p-4 border-l border-border align-top text-xs text-muted-foreground leading-relaxed">
                  {p.description || "No detailed overview provided."}
                </td>
              ))}
            </tr>

            {/* Technical Specifications Rows */}
            {attributeKeys.map((attrKey) => (
              <tr key={attrKey} className="hover:bg-muted/20">
                <td className="p-4 font-semibold text-foreground bg-muted/20 capitalize">
                  {attrKey.replace(/_/g, " ")}
                </td>
                {products.map((p) => {
                  const primaryVariant = p.variants[0];
                  const val = primaryVariant?.attributes?.[attrKey];

                  return (
                    <td key={p.id} className="p-4 border-l border-border align-top text-xs">
                      {val !== undefined && val !== null && val !== "" ? (
                        <span className="font-medium text-foreground">{String(val)}</span>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
