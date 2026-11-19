"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  PlusCircle,
  Search,
  CheckCircle2,
  AlertCircle,
  Layers,
  ChevronRight,
  Package,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiClient, ApiClientError } from "@/lib/api/client";
import type { CatalogueLookupProduct, CatalogueLookupVariant, RetailerListingCreatePayload } from "@/types";

export default function NewRetailerListingPage() {
  const router = useRouter();
  const [products, setProducts] = useState<CatalogueLookupProduct[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Selection & Form State
  const [selectedProduct, setSelectedProduct] = useState<CatalogueLookupProduct | null>(null);
  const [selectedVariant, setSelectedVariant] = useState<CatalogueLookupVariant | null>(null);
  const [originalPriceRupees, setOriginalPriceRupees] = useState("");
  const [sellingPriceRupees, setSellingPriceRupees] = useState("");
  const [sellerSku, setSellerSku] = useState("");
  const [initialStock, setInitialStock] = useState("25");
  const [lowStockThreshold, setLowStockThreshold] = useState("5");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const loadCatalogue = useCallback(async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const data = await apiClient.getRetailerCatalogueProducts({
        search: searchQuery.trim() || undefined,
        limit: 50,
      });
      setProducts(data);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to load platform catalogue.");
    } finally {
      setIsLoading(false);
    }
  }, [searchQuery]);

  useEffect(() => {
    loadCatalogue();
  }, [loadCatalogue]);

  const handleSelectVariant = (prod: CatalogueLookupProduct, v: CatalogueLookupVariant) => {
    if (v.is_already_listed) return;
    setSelectedProduct(prod);
    setSelectedVariant(v);
    setFormError(null);
  };

  const handleCreateListing = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedVariant) return;

    const originalVal = parseFloat(originalPriceRupees);
    const sellingVal = parseFloat(sellingPriceRupees);
    const stockVal = parseInt(initialStock, 10);
    const thresholdVal = parseInt(lowStockThreshold, 10);

    if (isNaN(originalVal) || originalVal < 0) {
      setFormError("Please enter a valid MRP in rupees.");
      return;
    }
    if (isNaN(sellingVal) || sellingVal < 0) {
      setFormError("Please enter a valid selling price in rupees.");
      return;
    }
    if (sellingVal > originalVal) {
      setFormError("Selling price cannot exceed the original MRP price.");
      return;
    }
    if (isNaN(stockVal) || stockVal < 0) {
      setFormError("Initial stock must be a non-negative number.");
      return;
    }

    setIsSubmitting(true);
    setFormError(null);

    try {
      const payload: RetailerListingCreatePayload = {
        variant_id: selectedVariant.id,
        seller_sku: sellerSku.trim() || undefined,
        original_price_paise: Math.round(originalVal * 100),
        selling_price_paise: Math.round(sellingVal * 100),
        initial_on_hand_quantity: stockVal,
        low_stock_threshold: isNaN(thresholdVal) ? 10 : thresholdVal,
        is_active: true,
      };

      await apiClient.createRetailerListing(payload);
      router.push("/retailer/listings");
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setFormError(err.message);
      } else {
        setFormError(err instanceof Error ? err.message : "Failed to create listing.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Back button & Title */}
      <div className="flex items-center gap-3">
        <Link href="/retailer/listings">
          <Button variant="outline" size="sm" className="h-8 w-8 p-0">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <PlusCircle className="h-5 w-5 text-blue-600" />
            Add Catalogue Product to Your Store
          </h1>
          <p className="text-xs text-muted-foreground">
            Select a verified platform product variant, specify your store selling price, and set initial inventory.
          </p>
        </div>
      </div>

      {errorMsg && (
        <div className="p-3 rounded-lg border border-red-500/30 bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 text-xs flex items-center gap-2">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Catalogue Search & Variant Picker */}
        <div className="lg:col-span-7 space-y-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search canonical products or brands..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 text-xs"
            />
          </div>

          <div className="space-y-3 max-h-[620px] overflow-y-auto pr-1">
            {isLoading ? (
              <div className="p-8 text-center text-muted-foreground text-xs">
                Loading platform catalogue products...
              </div>
            ) : products.length === 0 ? (
              <div className="p-8 text-center text-muted-foreground text-xs border rounded-xl bg-card">
                No matching canonical products found.
              </div>
            ) : (
              products.map((prod) => (
                <div
                  key={prod.id}
                  className="rounded-xl border bg-card p-4 shadow-xs space-y-3 hover:border-blue-500/40 transition-colors"
                >
                  <div className="flex items-start gap-3">
                    {prod.image_url ? (
                      <img
                        src={prod.image_url}
                        alt={prod.name}
                        className="h-12 w-12 rounded-lg object-cover border bg-muted shrink-0"
                      />
                    ) : (
                      <div className="h-12 w-12 rounded-lg bg-muted flex items-center justify-center text-muted-foreground shrink-0">
                        <Package className="h-6 w-6" />
                      </div>
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-[10px] uppercase tracking-wider py-0 px-1.5">
                          {prod.category_name}
                        </Badge>
                        <span className="text-xs text-muted-foreground font-medium">{prod.brand}</span>
                      </div>
                      <h4 className="font-semibold text-foreground text-sm truncate mt-0.5">{prod.name}</h4>
                    </div>
                  </div>

                  {/* Variants List for Product */}
                  <div className="border-t pt-2.5 space-y-1.5">
                    <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                      Select Variant to List:
                    </span>
                    <div className="grid grid-cols-1 gap-1.5">
                      {prod.variants.map((v) => {
                        const isSelected = selectedVariant?.id === v.id;
                        return (
                          <button
                            key={v.id}
                            disabled={v.is_already_listed}
                            onClick={() => handleSelectVariant(prod, v)}
                            className={`w-full text-left p-2.5 rounded-lg border text-xs flex items-center justify-between transition-all ${
                              v.is_already_listed
                                ? "bg-muted/40 border-border text-muted-foreground opacity-60 cursor-not-allowed"
                                : isSelected
                                ? "bg-blue-50 border-blue-600 text-blue-900 dark:bg-blue-950/60 dark:text-blue-200 font-semibold shadow-xs"
                                : "bg-card hover:bg-muted/50 hover:border-border text-foreground"
                            }`}
                          >
                            <div className="space-y-0.5">
                              <div className="font-medium flex items-center gap-1.5">
                                {v.name}
                                {v.is_already_listed && (
                                  <Badge variant="outline" className="text-[9px] px-1 py-0 border-zinc-300">
                                    Already in Store
                                  </Badge>
                                )}
                              </div>
                              <div className="font-mono text-[10px] text-muted-foreground">SKU: {v.sku}</div>
                            </div>

                            {!v.is_already_listed && (
                              <ChevronRight
                                className={`h-4 w-4 ${
                                  isSelected ? "text-blue-600" : "text-muted-foreground"
                                }`}
                              />
                            )}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Right Column: Pricing & Inventory Form */}
        <div className="lg:col-span-5">
          <div className="rounded-xl border bg-card p-6 shadow-xs sticky top-6 space-y-4">
            <div>
              <h3 className="font-bold text-foreground text-sm">Store Listing Configuration</h3>
              <p className="text-xs text-muted-foreground">
                Set custom store pricing and initial stock for the selected variant.
              </p>
            </div>

            {selectedVariant ? (
              <form onSubmit={handleCreateListing} className="space-y-4 text-xs">
                {/* Selected Item Summary */}
                <div className="p-3 rounded-lg border border-blue-500/30 bg-blue-50/50 dark:bg-blue-950/30 space-y-1">
                  <div className="text-[10px] uppercase font-bold text-blue-700 dark:text-blue-300">
                    Selected Variant
                  </div>
                  <div className="font-bold text-foreground text-sm line-clamp-1">
                    {selectedProduct?.name}
                  </div>
                  <div className="text-xs text-muted-foreground font-medium">
                    {selectedVariant.name} • <span className="font-mono text-[11px]">{selectedVariant.sku}</span>
                  </div>
                </div>

                {formError && (
                  <div className="p-3 rounded-lg border border-red-500/30 bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 text-xs flex items-center gap-2">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    <span>{formError}</span>
                  </div>
                )}

                <div>
                  <label className="font-medium text-foreground block mb-1">
                    MRP (Maximum Retail Price in ₹) *
                  </label>
                  <Input
                    type="number"
                    step="0.01"
                    min="0"
                    placeholder="e.g. 1999.00"
                    value={originalPriceRupees}
                    onChange={(e) => setOriginalPriceRupees(e.target.value)}
                    required
                    className="font-mono text-sm"
                  />
                </div>

                <div>
                  <label className="font-medium text-foreground block mb-1">
                    Store Selling Price (in ₹) *
                  </label>
                  <Input
                    type="number"
                    step="0.01"
                    min="0"
                    placeholder="e.g. 1749.00"
                    value={sellingPriceRupees}
                    onChange={(e) => setSellingPriceRupees(e.target.value)}
                    required
                    className="font-mono text-sm font-semibold text-emerald-600"
                  />
                  <span className="text-[10px] text-muted-foreground">
                    Must be less than or equal to MRP.
                  </span>
                </div>

                <div>
                  <label className="font-medium text-foreground block mb-1">
                    Custom Store SKU (Optional)
                  </label>
                  <Input
                    type="text"
                    placeholder="e.g. BLR-INV-042"
                    value={sellerSku}
                    onChange={(e) => setSellerSku(e.target.value)}
                    maxLength={100}
                    className="font-mono text-xs"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="font-medium text-foreground block mb-1">
                      Initial Stock (Units) *
                    </label>
                    <Input
                      type="number"
                      min="0"
                      value={initialStock}
                      onChange={(e) => setInitialStock(e.target.value)}
                      required
                      className="font-mono text-sm"
                    />
                  </div>
                  <div>
                    <label className="font-medium text-foreground block mb-1">
                      Low Stock Alert *
                    </label>
                    <Input
                      type="number"
                      min="0"
                      value={lowStockThreshold}
                      onChange={(e) => setLowStockThreshold(e.target.value)}
                      required
                      className="font-mono text-sm"
                    />
                  </div>
                </div>

                <Button
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium gap-2 shadow-xs"
                >
                  {isSubmitting ? "Publishing Listing..." : "Publish Product Listing"}
                </Button>
              </form>
            ) : (
              <div className="p-8 text-center space-y-2 border border-dashed rounded-xl text-muted-foreground text-xs">
                <Layers className="h-8 w-8 mx-auto text-zinc-400" />
                <p className="font-medium text-foreground">No Variant Selected</p>
                <p>Click on any available variant from the platform catalogue on the left to configure pricing.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
