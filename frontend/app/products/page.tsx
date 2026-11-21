"use client";

import { useEffect, useState, useTransition, useCallback, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ProductCard } from "@/components/catalogue/product-card";
import { ProductFilters } from "@/components/catalogue/product-filters";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api/client";
import type { Category, ProductSummary, Retailer } from "@/types";
import {
  ChevronLeft,
  ChevronRight,
  Filter,
  Loader2,
  PackageSearch,
  SlidersHorizontal,
  X,
} from "lucide-react";
import { useLiveUpdates } from "@/lib/realtime";

function ProductsView() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();

  // URL state
  const currentCategory = searchParams.get("category_slug") || "";
  const currentRetailer = searchParams.get("retailer_id") || "";
  const currentSearch = searchParams.get("search") || "";
  const currentMinPrice = searchParams.get("min_price") || "";
  const currentMaxPrice = searchParams.get("max_price") || "";
  const currentInStock = searchParams.get("in_stock") === "true";
  const currentSort = (searchParams.get("sort_by") as "newest" | "price_asc" | "price_desc" | "name_asc") || "newest";
  const currentPage = parseInt(searchParams.get("page") || "1", 10);

  // Local state
  const [products, setProducts] = useState<ProductSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [categories, setCategories] = useState<Category[]>([]);
  const [retailers, setRetailers] = useState<Retailer[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mobileFilterOpen, setMobileFilterOpen] = useState(false);

  // Fetch filter metadata (categories, retailers)
  useEffect(() => {
    async function loadMeta() {
      try {
        const [cats, rets] = await Promise.all([
          apiClient.getCategories(),
          apiClient.getRetailers(),
        ]);
        setCategories(cats);
        setRetailers(rets);
      } catch (err) {
        console.error("Failed to load filter metadata:", err);
      }
    }
    loadMeta();
  }, []);

  // Fetch products matching filters
  const loadProducts = useCallback(async (opts?: { quiet?: boolean }) => {
    if (!opts?.quiet) setIsLoading(true);
    setError(null);
    try {
      const minPricePaise = currentMinPrice ? parseInt(currentMinPrice, 10) * 100 : undefined;
      const maxPricePaise = currentMaxPrice ? parseInt(currentMaxPrice, 10) * 100 : undefined;

      const res = await apiClient.getProducts({
        category_slug: currentCategory || undefined,
        retailer_id: currentRetailer || undefined,
        search: currentSearch || undefined,
        min_price: minPricePaise,
        max_price: maxPricePaise,
        in_stock: currentInStock || undefined,
        sort_by: currentSort,
        page: currentPage,
        limit: 12,
      });

      setProducts(res.items);
      setTotal(res.total);
      setTotalPages(res.pages);
    } catch (err) {
      console.error("Failed to fetch products:", err);
      setError("Unable to load products. Ensure the backend service is running.");
    } finally {
      setIsLoading(false);
    }
  }, [
    currentCategory,
    currentRetailer,
    currentSearch,
    currentMinPrice,
    currentMaxPrice,
    currentInStock,
    currentSort,
    currentPage,
  ]);
  useLiveUpdates(["product.", "catalogue.", "listing.", "variant.", "price.", "inventory.", "store_inventory.", "offer.", "sale_stream."], () => void loadProducts({ quiet: true }));

  useEffect(() => {
    loadProducts();
  }, [loadProducts]);

  // Update URL helper
  const updateQuery = (updates: Record<string, string | null>) => {
    const params = new URLSearchParams(searchParams.toString());
    Object.entries(updates).forEach(([key, value]) => {
      if (value === null || value === "") {
        params.delete(key);
      } else {
        params.set(key, value);
      }
    });

    // Reset page to 1 whenever filters change (unless page is explicitly changed)
    if (!("page" in updates)) {
      params.delete("page");
    }

    startTransition(() => {
      router.push(`/products?${params.toString()}`);
    });
  };

  const handleClearFilters = () => {
    startTransition(() => {
      router.push("/products");
    });
  };

  return (
    <div className="container mx-auto px-4 py-8 sm:px-6 space-y-6">
      {/* Header and Filter summary */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between pb-4 border-b">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
              Catalogue
            </h1>
            <Badge variant="outline" className="text-xs">
              {total} {total === 1 ? "product" : "products"}
            </Badge>
          </div>
          <p className="text-xs sm:text-sm text-muted-foreground mt-1">
            {currentSearch ? (
              <span>
                Search results for <strong className="text-foreground">&ldquo;{currentSearch}&rdquo;</strong>
              </span>
            ) : currentCategory ? (
              <span>
                Filtered by category: <strong className="text-foreground capitalize">{currentCategory.replace("-", " ")}</strong>
              </span>
            ) : (
              "All categories, brands, and retail listings"
            )}
          </p>
        </div>

        {/* Controls: Sort and Mobile Filter Toggle */}
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setMobileFilterOpen(true)}
            className="md:hidden flex items-center gap-1.5 text-xs"
          >
            <Filter className="h-3.5 w-3.5" />
            Filters
          </Button>

          <div className="flex items-center gap-2">
            <SlidersHorizontal className="h-4 w-4 text-muted-foreground hidden sm:block" />
            <select
              value={currentSort}
              onChange={(e) => updateQuery({ sort_by: e.target.value })}
              className="h-9 rounded-md border border-input bg-background px-3 py-1 text-xs sm:text-sm shadow-xs focus:outline-none focus:ring-2 focus:ring-emerald-500"
            >
              <option value="newest">Newest First</option>
              <option value="price_asc">Price: Low to High</option>
              <option value="price_desc">Price: High to Low</option>
              <option value="name_asc">Name: A to Z</option>
            </select>
          </div>
        </div>
      </div>

      {/* Main Grid: Sidebar + Product Grid */}
      <div className="grid grid-cols-1 gap-8 md:grid-cols-4 lg:grid-cols-5">
        {/* Desktop Filter Sidebar */}
        <aside className="hidden md:block md:col-span-1 border-r pr-6">
          <ProductFilters
            categories={categories}
            retailers={retailers}
            selectedCategory={currentCategory}
            selectedRetailer={currentRetailer}
            minPrice={currentMinPrice}
            maxPrice={currentMaxPrice}
            inStockOnly={currentInStock}
            onCategoryChange={(slug) => updateQuery({ category_slug: slug })}
            onRetailerChange={(id) => updateQuery({ retailer_id: id })}
            onMinPriceChange={(val) => updateQuery({ min_price: val })}
            onMaxPriceChange={(val) => updateQuery({ max_price: val })}
            onInStockToggle={() => updateQuery({ in_stock: currentInStock ? null : "true" })}
            onClearFilters={handleClearFilters}
          />
        </aside>

        {/* Mobile Filter Sheet Modal */}
        {mobileFilterOpen && (
          <div className="fixed inset-0 z-50 flex md:hidden bg-background/80 backdrop-blur-sm">
            <div className="relative ml-auto h-full w-full max-w-xs bg-background p-6 shadow-xl border-l overflow-y-auto">
              <div className="flex items-center justify-between pb-4 border-b mb-4">
                <span className="font-bold text-base">Filter Products</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setMobileFilterOpen(false)}
                  className="h-8 w-8 p-0"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>

              <ProductFilters
                categories={categories}
                retailers={retailers}
                selectedCategory={currentCategory}
                selectedRetailer={currentRetailer}
                minPrice={currentMinPrice}
                maxPrice={currentMaxPrice}
                inStockOnly={currentInStock}
                onCategoryChange={(slug) => {
                  updateQuery({ category_slug: slug });
                  setMobileFilterOpen(false);
                }}
                onRetailerChange={(id) => {
                  updateQuery({ retailer_id: id });
                  setMobileFilterOpen(false);
                }}
                onMinPriceChange={(val) => updateQuery({ min_price: val })}
                onMaxPriceChange={(val) => updateQuery({ max_price: val })}
                onInStockToggle={() => updateQuery({ in_stock: currentInStock ? null : "true" })}
                onClearFilters={() => {
                  handleClearFilters();
                  setMobileFilterOpen(false);
                }}
              />
            </div>
          </div>
        )}

        {/* Product Cards Container */}
        <main className="md:col-span-3 lg:col-span-4 space-y-8">
          {isLoading || isPending ? (
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {Array.from({ length: 8 }).map((_, i) => (
                <div
                  key={i}
                  className="rounded-xl border bg-muted/20 p-4 space-y-4 animate-pulse"
                >
                  <div className="aspect-square w-full rounded-lg bg-muted/60" />
                  <div className="h-4 w-2/3 bg-muted/60 rounded" />
                  <div className="h-4 w-full bg-muted/60 rounded" />
                  <div className="h-6 w-1/3 bg-muted/60 rounded" />
                </div>
              ))}
            </div>
          ) : error ? (
            <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-12 text-center space-y-4">
              <p className="text-sm font-medium text-destructive">{error}</p>
              <Button size="sm" onClick={() => loadProducts()} variant="outline">
                Retry
              </Button>
            </div>
          ) : products.length === 0 ? (
            <div className="rounded-2xl border border-dashed p-16 text-center space-y-4">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-muted text-muted-foreground">
                <PackageSearch className="h-7 w-7" />
              </div>
              <div className="space-y-1">
                <h3 className="font-bold text-lg text-foreground">No Products Found</h3>
                <p className="text-xs sm:text-sm text-muted-foreground max-w-md mx-auto">
                  We could not find any products matching your selected criteria. Try clearing filters or searching for something else.
                </p>
              </div>
              <Button size="sm" onClick={handleClearFilters} className="mt-2">
                Reset All Filters
              </Button>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {products.map((product) => (
                  <ProductCard key={product.id} product={product} />
                ))}
              </div>

              {/* Pagination Bar */}
              {totalPages > 1 && (
                <div className="flex items-center justify-center space-x-2 pt-6 border-t">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={currentPage <= 1}
                    onClick={() => updateQuery({ page: (currentPage - 1).toString() })}
                    className="h-9 px-3"
                  >
                    <ChevronLeft className="h-4 w-4 mr-1" />
                    Previous
                  </Button>

                  <span className="text-xs sm:text-sm font-medium text-muted-foreground px-3">
                    Page {currentPage} of {totalPages}
                  </span>

                  <Button
                    variant="outline"
                    size="sm"
                    disabled={currentPage >= totalPages}
                    onClick={() => updateQuery({ page: (currentPage + 1).toString() })}
                    className="h-9 px-3"
                  >
                    Next
                    <ChevronRight className="h-4 w-4 ml-1" />
                  </Button>
                </div>
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
}

export default function ProductsPage() {
  return (
    <Suspense
      fallback={
        <div className="container mx-auto px-4 py-16 flex items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-emerald-600" />
        </div>
      }
    >
      <ProductsView />
    </Suspense>
  );
}
