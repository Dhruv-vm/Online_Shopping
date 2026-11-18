"use client";

import { useEffect, useState, useTransition, useCallback, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { ProductCard } from "@/components/catalogue/product-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiClient } from "@/lib/api/client";
import type {
  ProductSearchItem,
  ProductSummary,
  SearchFacets,
  SearchResponse,
} from "@/types";
import {
  ChevronLeft,
  ChevronRight,
  Filter,
  Loader2,
  PackageSearch,
  Search,
  SlidersHorizontal,
  Sparkles,
  Database,
  X,
} from "lucide-react";

function SearchView() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [, startTransition] = useTransition();

  // Search params
  const currentQuery = searchParams.get("q") || "";
  const currentCategory = searchParams.get("category") || "";
  const currentBrand = searchParams.get("brand") || "";
  const currentRetailer = searchParams.get("retailer_id") || "";
  const currentMinPrice = searchParams.get("min_price") || "";
  const currentMaxPrice = searchParams.get("max_price") || "";
  const currentInStock = searchParams.get("in_stock") === "true";
  const currentSort =
    (searchParams.get("sort") as
      | "relevance"
      | "price_asc"
      | "price_desc"
      | "rating_desc"
      | "newest") || "relevance";
  const currentPage = parseInt(searchParams.get("page") || "1", 10);

  // Search input local state
  const [searchInput, setSearchInput] = useState(currentQuery);
  const [results, setResults] = useState<ProductSearchItem[]>([]);
  const [facets, setFacets] = useState<SearchFacets | null>(null);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [engine, setEngine] = useState<"opensearch" | "postgres_fallback">("opensearch");
  const [tookMs, setTookMs] = useState<number | undefined>(undefined);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mobileFilterOpen, setMobileFilterOpen] = useState(false);

  // Sync search input when URL changes
  useEffect(() => {
    setSearchInput(currentQuery);
  }, [currentQuery]);

  // Execute Search
  const executeSearch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const minPricePaise = currentMinPrice
        ? parseInt(currentMinPrice, 10) * 100
        : undefined;
      const maxPricePaise = currentMaxPrice
        ? parseInt(currentMaxPrice, 10) * 100
        : undefined;

      const res: SearchResponse = await apiClient.searchProducts({
        q: currentQuery || undefined,
        category: currentCategory || undefined,
        brand: currentBrand || undefined,
        retailer_id: currentRetailer || undefined,
        min_price: minPricePaise,
        max_price: maxPricePaise,
        in_stock: currentInStock || undefined,
        sort: currentSort,
        page: currentPage,
        page_size: 16,
      });

      setResults(res.items);
      setFacets(res.facets || null);
      setTotal(res.total);
      setTotalPages(res.total_pages);
      setEngine(res.engine);
      setTookMs(res.took_ms);
    } catch (err: unknown) {
      console.error("Search execution failed:", err);
      setError("Unable to complete search. Please try again.");
    } finally {
      setIsLoading(false);
    }
  }, [
    currentQuery,
    currentCategory,
    currentBrand,
    currentRetailer,
    currentMinPrice,
    currentMaxPrice,
    currentInStock,
    currentSort,
    currentPage,
  ]);

  useEffect(() => {
    executeSearch();
  }, [executeSearch]);

  // URL updater
  const updateUrl = (updates: Record<string, string | undefined>) => {
    const params = new URLSearchParams(searchParams.toString());
    Object.entries(updates).forEach(([key, value]) => {
      if (value === undefined || value === "") {
        params.delete(key);
      } else {
        params.set(key, value);
      }
    });
    // Reset to page 1 on filter or query changes (unless changing page itself)
    if (!("page" in updates)) {
      params.delete("page");
    }
    startTransition(() => {
      router.push(`/search?${params.toString()}`);
    });
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    updateUrl({ q: searchInput.trim() || undefined });
  };

  const clearAllFilters = () => {
    const params = new URLSearchParams();
    if (currentQuery) params.set("q", currentQuery);
    startTransition(() => {
      router.push(`/search?${params.toString()}`);
    });
  };

  const activeFilterCount = [
    currentCategory,
    currentBrand,
    currentRetailer,
    currentMinPrice,
    currentMaxPrice,
    currentInStock,
  ].filter(Boolean).length;

  return (
    <div className="container max-w-7xl mx-auto px-4 py-8">
      {/* Top Search Bar & Header */}
      <div className="mb-8">
        <form onSubmit={handleSearchSubmit} className="relative flex max-w-2xl mx-auto gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-3 h-5 w-5 text-muted-foreground" />
            <Input
              type="search"
              placeholder="Search across all categories, brands, and retailers..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="pl-10 pr-4 h-11 text-base bg-background shadow-xs border-muted-foreground/30 focus-visible:ring-emerald-500"
            />
          </div>
          <Button type="submit" className="h-11 px-6 bg-emerald-600 hover:bg-emerald-700 text-white font-medium">
            Search
          </Button>
        </form>

        <div className="mt-6 flex flex-wrap items-center justify-between gap-4 border-b pb-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              {currentQuery ? (
                <>
                  Results for <span className="text-emerald-600">&ldquo;{currentQuery}&rdquo;</span>
                </>
              ) : (
                "Universal Product Search"
              )}
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              Found {total} {total === 1 ? "product" : "products"} across all verified sellers
            </p>
          </div>

          <div className="flex items-center gap-3">
            {/* Search Engine Mode Badge */}
            {engine === "opensearch" ? (
              <Badge
                variant="outline"
                className="bg-emerald-50 text-emerald-700 border-emerald-200 flex items-center gap-1.5 px-3 py-1 font-mono text-xs"
              >
                <Sparkles className="h-3.5 w-3.5 text-emerald-600" />
                OpenSearch Instant {tookMs !== undefined ? `(${tookMs}ms)` : ""}
              </Badge>
            ) : (
              <Badge
                variant="outline"
                className="bg-amber-50 text-amber-800 border-amber-300 flex items-center gap-1.5 px-3 py-1 font-mono text-xs"
              >
                <Database className="h-3.5 w-3.5 text-amber-600" />
                SQL Fallback Active
              </Badge>
            )}

            {/* Sort Selector */}
            <select
              value={currentSort}
              onChange={(e) => updateUrl({ sort: e.target.value })}
              className="h-9 rounded-md border border-input bg-background px-3 py-1 text-xs shadow-xs focus:outline-none focus:ring-1 focus:ring-emerald-500"
            >
              <option value="relevance">Most Relevant</option>
              <option value="price_asc">Price: Low to High</option>
              <option value="price_desc">Price: High to Low</option>
              <option value="rating_desc">Highest Rated</option>
              <option value="newest">Newest Arrivals</option>
            </select>

            {/* Mobile Filter Toggle */}
            <Button
              variant="outline"
              size="sm"
              className="lg:hidden flex items-center gap-2"
              onClick={() => setMobileFilterOpen(true)}
            >
              <SlidersHorizontal className="h-4 w-4" />
              Filters
              {activeFilterCount > 0 && (
                <Badge variant="secondary" className="ml-1 px-1.5 py-0.5 text-xs bg-emerald-100 text-emerald-800">
                  {activeFilterCount}
                </Badge>
              )}
            </Button>
          </div>
        </div>
      </div>

      {/* Main Grid: Sidebar Filters + Product List */}
      <div className="flex gap-8">
        {/* Desktop Sidebar Filters */}
        <aside className="hidden lg:block w-64 shrink-0 space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
              <Filter className="h-4 w-4" />
              Filters
            </h2>
            {activeFilterCount > 0 && (
              <button
                onClick={clearAllFilters}
                className="text-xs text-emerald-600 hover:text-emerald-700 font-medium"
              >
                Reset All
              </button>
            )}
          </div>

          {/* In Stock Toggle */}
          <div className="space-y-2 border-b pb-4">
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={currentInStock}
                onChange={(e) => updateUrl({ in_stock: e.target.checked ? "true" : undefined })}
                className="rounded border-gray-300 text-emerald-600 focus:ring-emerald-500"
              />
              <span className="font-medium text-foreground">In Stock Only</span>
            </label>
          </div>

          {/* Facets: Categories */}
          {facets?.categories && facets.categories.length > 0 && (
            <div className="space-y-3 border-b pb-5">
              <h3 className="text-xs font-bold uppercase tracking-wider text-foreground">Categories</h3>
              <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                {facets.categories.map((c) => (
                  <button
                    key={c.key}
                    onClick={() =>
                      updateUrl({
                        category: currentCategory === c.key.toLowerCase().replace(/\s+/g, "-") ? undefined : c.key.toLowerCase().replace(/\s+/g, "-"),
                      })
                    }
                    className="flex w-full items-center justify-between text-xs py-1 text-muted-foreground hover:text-foreground text-left"
                  >
                    <span className="truncate pr-2">{c.key}</span>
                    <Badge variant="secondary" className="text-[10px] px-1.5 py-0 font-normal">
                      {c.doc_count}
                    </Badge>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Facets: Brands */}
          {facets?.brands && facets.brands.length > 0 && (
            <div className="space-y-3 border-b pb-5">
              <h3 className="text-xs font-bold uppercase tracking-wider text-foreground">Brands</h3>
              <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                {facets.brands.map((b) => (
                  <button
                    key={b.key}
                    onClick={() => updateUrl({ brand: currentBrand === b.key ? undefined : b.key })}
                    className={`flex w-full items-center justify-between text-xs py-1 text-left ${
                      currentBrand === b.key
                        ? "text-emerald-600 font-semibold"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    <span className="truncate pr-2">{b.key}</span>
                    <Badge variant="secondary" className="text-[10px] px-1.5 py-0 font-normal">
                      {b.doc_count}
                    </Badge>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Price Range Filter */}
          <div className="space-y-3 pb-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-foreground">Price (₹)</h3>
            <div className="flex items-center gap-2">
              <Input
                type="number"
                placeholder="Min"
                value={currentMinPrice}
                onChange={(e) => updateUrl({ min_price: e.target.value || undefined })}
                className="h-8 text-xs"
              />
              <span className="text-muted-foreground">-</span>
              <Input
                type="number"
                placeholder="Max"
                value={currentMaxPrice}
                onChange={(e) => updateUrl({ max_price: e.target.value || undefined })}
                className="h-8 text-xs"
              />
            </div>
          </div>
        </aside>

        {/* Product Results Grid */}
        <main className="flex-1 min-w-0">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-24 text-muted-foreground">
              <Loader2 className="h-8 w-8 animate-spin text-emerald-600 mb-3" />
              <p className="text-sm">Searching verified catalog...</p>
            </div>
          ) : error ? (
            <div className="text-center py-20 bg-destructive/10 rounded-xl p-8 border border-destructive/20">
              <p className="text-destructive font-medium mb-3">{error}</p>
              <Button onClick={() => executeSearch()} variant="outline" size="sm">
                Try Again
              </Button>
            </div>
          ) : results.length === 0 ? (
            <div className="text-center py-24 border border-dashed rounded-xl p-8">
              <PackageSearch className="h-12 w-12 text-muted-foreground mx-auto mb-4 stroke-1" />
              <h3 className="text-lg font-semibold mb-1">No matching products found</h3>
              <p className="text-sm text-muted-foreground max-w-md mx-auto mb-6">
                Try adjusting your search terms, removing filters, or browsing our full catalogue.
              </p>
              <div className="flex justify-center gap-3">
                {activeFilterCount > 0 && (
                  <Button onClick={clearAllFilters} variant="outline" size="sm">
                    Clear Filters
                  </Button>
                )}
                <Link
                  href="/products"
                  className="inline-flex items-center justify-center rounded-md text-sm font-medium h-9 px-3 bg-emerald-600 hover:bg-emerald-700 text-white transition-colors"
                >
                  Browse All Products
                </Link>
              </div>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4">
                {results.map((p) => {
                  const summary: ProductSummary = {
                    id: String(p.product_id),
                    name: p.name,
                    slug: p.slug,
                    brand: p.brand,
                    category_id: p.category_id || "",
                    category_name: p.category_name || "",
                    category_slug: p.category_slug || "",
                    primary_image: p.primary_image_url || null,
                    min_price_paise: p.min_price_paise,
                    max_price_paise: p.max_price_paise,
                    original_price_paise:
                      p.max_price_paise > p.min_price_paise
                        ? p.max_price_paise
                        : null,
                    currency: p.currency || "INR",
                    is_in_stock: p.is_in_stock,
                    variant_count: p.variants.length,
                    retailer_count: p.retailers.length,
                  };
                  return <ProductCard key={p.product_id} product={summary} />;
                })}
              </div>

              {/* Pagination Controls */}
              {totalPages > 1 && (
                <div className="mt-10 flex items-center justify-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={currentPage <= 1}
                    onClick={() => updateUrl({ page: String(currentPage - 1) })}
                  >
                    <ChevronLeft className="h-4 w-4 mr-1" />
                    Previous
                  </Button>
                  <span className="text-sm text-muted-foreground px-3">
                    Page {currentPage} of {totalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={currentPage >= totalPages}
                    onClick={() => updateUrl({ page: String(currentPage + 1) })}
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

      {/* Mobile Filters Drawer */}
      {mobileFilterOpen && (
        <div className="fixed inset-0 z-50 flex lg:hidden">
          <div className="fixed inset-0 bg-black/50" onClick={() => setMobileFilterOpen(false)} />
          <div className="relative ml-auto w-full max-w-xs bg-background h-full p-6 shadow-xl flex flex-col justify-between overflow-y-auto">
            <div>
              <div className="flex items-center justify-between pb-4 border-b">
                <h3 className="font-semibold text-lg">Filter Products</h3>
                <Button variant="ghost" size="icon" onClick={() => setMobileFilterOpen(false)}>
                  <X className="h-5 w-5" />
                </Button>
              </div>

              <div className="py-4 space-y-6">
                <label className="flex items-center gap-2 text-sm font-medium">
                  <input
                    type="checkbox"
                    checked={currentInStock}
                    onChange={(e) => updateUrl({ in_stock: e.target.checked ? "true" : undefined })}
                    className="rounded border-gray-300 text-emerald-600 focus:ring-emerald-500"
                  />
                  In Stock Only
                </label>

                {facets?.brands && facets.brands.length > 0 && (
                  <div>
                    <h4 className="text-xs font-bold uppercase text-muted-foreground mb-2">Brands</h4>
                    <div className="space-y-1.5 max-h-40 overflow-y-auto">
                      {facets.brands.map((b) => (
                        <button
                          key={b.key}
                          onClick={() => {
                            updateUrl({ brand: currentBrand === b.key ? undefined : b.key });
                            setMobileFilterOpen(false);
                          }}
                          className={`text-xs block w-full text-left py-1 ${
                            currentBrand === b.key ? "text-emerald-600 font-bold" : "text-muted-foreground"
                          }`}
                        >
                          {b.key} ({b.doc_count})
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div className="border-t pt-4 flex gap-2">
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => {
                  clearAllFilters();
                  setMobileFilterOpen(false);
                }}
              >
                Reset
              </Button>
              <Button
                className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white"
                onClick={() => setMobileFilterOpen(false)}
              >
                Apply
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense
      fallback={
        <div className="container max-w-7xl mx-auto px-4 py-16 flex justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-emerald-600" />
        </div>
      }
    >
      <SearchView />
    </Suspense>
  );
}
