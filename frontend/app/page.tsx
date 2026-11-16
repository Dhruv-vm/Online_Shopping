import Link from "next/link";
import { CategoryCard } from "@/components/catalogue/category-card";
import { ProductCard } from "@/components/catalogue/product-card";
import { SystemStatus } from "@/components/shared/system-status";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api/client";
import type { Category, ProductSummary, Retailer } from "@/types";
import { ArrowRight, Sparkles, Store, ShieldCheck, Zap } from "lucide-react";

export const revalidate = 0; // Dynamic data

async function getHomeData() {
  try {
    const [categories, productsData, retailers] = await Promise.all([
      apiClient.getCategories().catch(() => [] as Category[]),
      apiClient.getProducts({ limit: 8, sort_by: "newest" }).catch(() => ({ items: [] as ProductSummary[], total: 0, page: 1, limit: 8, pages: 1 })),
      apiClient.getRetailers().catch(() => [] as Retailer[]),
    ]);

    return {
      categories,
      featuredProducts: productsData.items,
      retailers,
    };
  } catch (e) {
    console.error("Error loading home data:", e);
    return {
      categories: [],
      featuredProducts: [],
      retailers: [],
    };
  }
}

export default async function HomePage() {
  const { categories, featuredProducts, retailers } = await getHomeData();

  return (
    <div className="container mx-auto space-y-16 px-4 py-8 sm:px-6">
      {/* Hero Showcase Section */}
      <section className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-emerald-950 via-teal-900 to-slate-900 px-6 py-14 sm:px-12 sm:py-20 text-white shadow-xl">
        <div className="relative z-10 max-w-2xl space-y-6">
          <div className="flex items-center gap-2">
            <Badge className="bg-emerald-500/20 text-emerald-300 border-emerald-400/30 backdrop-blur-md px-3 py-1 text-xs">
              <Sparkles className="h-3.5 w-3.5 mr-1" />
              Phase 1 Live Storefront
            </Badge>
            <span className="text-xs text-emerald-200/80 font-medium">
              Multi-Retailer Marketplace
            </span>
          </div>

          <h1 className="text-3xl font-extrabold tracking-tight sm:text-5xl sm:leading-tight">
            Universal Online Shopping Across India.
          </h1>

          <p className="text-base sm:text-lg text-emerald-100/90 leading-relaxed">
            Discover verified electronics, hand-crafted fashion, gourmet pantry, and wellness essentials from top Indian retailers with real-time stock and transparent pricing.
          </p>

          <div className="flex flex-wrap items-center gap-3 pt-2">
            <Link href="/products">
              <Button size="lg" className="bg-emerald-500 text-slate-950 font-semibold hover:bg-emerald-400 transition-colors shadow-lg">
                Browse Full Catalogue
                <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            </Link>
            <Link href="/categories">
              <Button
                size="lg"
                className="bg-white/10 border-2 border-emerald-300/40 text-white font-semibold hover:bg-white/20 transition-colors shadow-sm"
              >
                Explore Categories
              </Button>
            </Link>
          </div>

          {/* Quick Category Badges */}
          <div className="flex flex-wrap items-center gap-2 pt-4">
            <span className="text-xs font-semibold text-emerald-200/70">Popular:</span>
            {categories.slice(0, 5).map((cat) => (
              <Link key={cat.id} href={`/products?category_slug=${cat.slug}`}>
                <Badge
                  variant="outline"
                  className="bg-white/10 hover:bg-white/20 text-white border-white/20 text-xs cursor-pointer transition-colors"
                >
                  {cat.name}
                </Badge>
              </Link>
            ))}
          </div>
        </div>

        {/* Decorative background glows */}
        <div className="absolute -right-20 -bottom-20 h-96 w-96 rounded-full bg-emerald-500/20 blur-3xl" />
        <div className="absolute right-1/3 -top-20 h-72 w-72 rounded-full bg-teal-400/10 blur-2xl" />
      </section>

      {/* Categories Grid */}
      <section className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
              Shop by Department
            </h2>
            <p className="text-sm text-muted-foreground mt-1">
              Curated catalogue spanning {categories.length} high-demand categories
            </p>
          </div>
          <Link
            href="/categories"
            className="flex items-center text-sm font-semibold text-emerald-600 hover:text-emerald-700 dark:hover:text-emerald-400 group"
          >
            All Departments
            <ArrowRight className="h-4 w-4 ml-1 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </div>

        <div className="grid grid-cols-2 gap-3.5 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-4 xl:grid-cols-7">
          {categories.map((category) => (
            <CategoryCard key={category.id} category={category} />
          ))}
        </div>
      </section>

      {/* Featured Products */}
      <section className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
                Featured Products
              </h2>
              <Badge variant="outline" className="text-xs text-emerald-600 border-emerald-600/30">
                Live Inventory
              </Badge>
            </div>
            <p className="text-sm text-muted-foreground mt-1">
              Top-rated selections verified across our multi-brand retail network
            </p>
          </div>
          <Link
            href="/products"
            className="flex items-center text-sm font-semibold text-emerald-600 hover:text-emerald-700 dark:hover:text-emerald-400 group"
          >
            View all {featuredProducts.length} items
            <ArrowRight className="h-4 w-4 ml-1 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </div>

        {featuredProducts.length > 0 ? (
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
            {featuredProducts.map((product) => (
              <ProductCard key={product.id} product={product} />
            ))}
          </div>
        ) : (
          <div className="rounded-xl border border-dashed p-10 text-center space-y-3">
            <p className="text-sm text-muted-foreground">
              No products found. Start the backend server and ensure seed data is applied.
            </p>
          </div>
        )}
      </section>

      {/* Retail Partners Showcase */}
      <section className="space-y-6 rounded-2xl bg-muted/30 p-6 sm:p-8 border">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-600 text-white">
              <Store className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-xl font-bold tracking-tight text-foreground">
                Authoritative Retail Partners
              </h3>
              <p className="text-xs sm:text-sm text-muted-foreground">
                Independent retail networks onboarded with direct inventory synchronization
              </p>
            </div>
          </div>
          <Link
            href="/retailers"
            className="text-xs sm:text-sm font-semibold text-emerald-600 hover:text-emerald-700 dark:hover:text-emerald-400"
          >
            View all partners
          </Link>
        </div>

        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-7 pt-2">
          {retailers.map((ret) => (
            <Link
              key={ret.id}
              href={`/products?retailer_id=${ret.id}`}
              className="flex flex-col items-center justify-center p-3 rounded-xl border bg-card hover:border-emerald-500/50 hover:shadow-xs transition-all text-center space-y-1.5"
            >
              <div className="font-semibold text-xs text-foreground truncate w-full">
                {ret.name}
              </div>
              <div className="flex items-center gap-1 text-[11px] text-amber-600 dark:text-amber-400 font-medium">
                ★ {ret.rating.toFixed(1)}
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* Platform Architecture Guarantees */}
      <section className="grid gap-6 sm:grid-cols-3 pt-4">
        <div className="flex gap-3.5 items-start p-4 rounded-xl border bg-card">
          <ShieldCheck className="h-6 w-6 text-emerald-600 shrink-0 mt-0.5" />
          <div className="space-y-1 text-xs">
            <h4 className="font-bold text-sm text-foreground">Authoritative PostgreSQL</h4>
            <p className="text-muted-foreground">
              Prices, inventory, and variant constraints are validated exclusively server-side.
            </p>
          </div>
        </div>

        <div className="flex gap-3.5 items-start p-4 rounded-xl border bg-card">
          <Zap className="h-6 w-6 text-purple-600 shrink-0 mt-0.5" />
          <div className="space-y-1 text-xs">
            <h4 className="font-bold text-sm text-foreground">Multi-Seller Competition</h4>
            <p className="text-muted-foreground">
              Compare transparent offers for the exact variant across competing retailers.
            </p>
          </div>
        </div>

        <div className="flex gap-3.5 items-start p-4 rounded-xl border bg-card">
          <Store className="h-6 w-6 text-blue-600 shrink-0 mt-0.5" />
          <div className="space-y-1 text-xs">
            <h4 className="font-bold text-sm text-foreground">Zero Dead Buttons</h4>
            <p className="text-muted-foreground">
              Every action in the customer journey maps to a live API and resilient error envelope.
            </p>
          </div>
        </div>
      </section>

      {/* System Status Section */}
      <section id="status">
        <SystemStatus />
      </section>
    </div>
  );
}
