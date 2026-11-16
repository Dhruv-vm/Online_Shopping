"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ShoppingBasket, Search, Menu, X, Store, LayoutGrid } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function Header() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState("");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      router.push(`/products?search=${encodeURIComponent(searchQuery.trim())}`);
      setMobileMenuOpen(false);
    }
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80 shadow-xs">
      <div className="container mx-auto flex h-16 items-center justify-between px-4 sm:px-6 gap-4">
        {/* Brand Logo */}
        <Link href="/" className="flex items-center space-x-2.5 shrink-0">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-600 text-white shadow-sm">
            <ShoppingBasket className="h-5 w-5" />
          </div>
          <div className="flex flex-col">
            <div className="flex items-center">
              <span className="text-xl font-extrabold tracking-tight text-foreground">
                BASKET
              </span>
              <Badge variant="outline" className="ml-2 font-mono text-[10px] text-emerald-700 dark:text-emerald-400 border-emerald-600/30">
                Live Store
              </Badge>
            </div>
            <span className="text-[10px] text-muted-foreground hidden sm:block">
              Multi-Category Indian Retail
            </span>
          </div>
        </Link>

        {/* Global Search Bar (Desktop) */}
        <form
          onSubmit={handleSearchSubmit}
          className="relative hidden md:flex flex-1 max-w-md mx-4 items-center"
        >
          <Search className="absolute left-3 h-4 w-4 text-muted-foreground pointer-events-none" />
          <Input
            type="search"
            placeholder="Search Sony headphones, FabIndia silk, organic groceries..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9 pr-4 h-10 w-full bg-muted/40 border-muted-foreground/20 focus:bg-background transition-colors text-xs sm:text-sm"
          />
        </form>

        {/* Desktop Navigation Links */}
        <nav className="hidden lg:flex items-center space-x-6 text-sm font-medium">
          <Link
            href="/products"
            className="flex items-center gap-1.5 text-muted-foreground transition-colors hover:text-emerald-700 dark:hover:text-emerald-400"
          >
            <LayoutGrid className="h-4 w-4" />
            Catalogue
          </Link>
          <Link
            href="/categories"
            className="text-muted-foreground transition-colors hover:text-emerald-700 dark:hover:text-emerald-400"
          >
            Categories
          </Link>
          <Link
            href="/retailers"
            className="flex items-center gap-1.5 text-muted-foreground transition-colors hover:text-emerald-700 dark:hover:text-emerald-400"
          >
            <Store className="h-4 w-4" />
            Retailers
          </Link>
          <Link
            href="/#status"
            className="text-muted-foreground transition-colors hover:text-emerald-700 dark:hover:text-emerald-400"
          >
            Status
          </Link>
        </nav>

        {/* Mobile menu trigger */}
        <div className="flex items-center md:hidden gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Toggle navigation"
            className="h-9 w-9 p-0"
          >
            {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </Button>
        </div>
      </div>

      {/* Mobile Navigation Drawer / Dropdown */}
      {mobileMenuOpen && (
        <div className="md:hidden border-t bg-background px-4 py-4 space-y-4">
          <form onSubmit={handleSearchSubmit} className="relative">
            <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
            <Input
              type="search"
              placeholder="Search products, brands, categories..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 pr-4 h-10 w-full"
            />
          </form>

          <nav className="flex flex-col space-y-2 text-sm font-medium pt-2">
            <Link
              href="/products"
              onClick={() => setMobileMenuOpen(false)}
              className="px-2 py-2 rounded-md hover:bg-muted text-foreground"
            >
              Browse All Products
            </Link>
            <Link
              href="/categories"
              onClick={() => setMobileMenuOpen(false)}
              className="px-2 py-2 rounded-md hover:bg-muted text-foreground"
            >
              Categories
            </Link>
            <Link
              href="/retailers"
              onClick={() => setMobileMenuOpen(false)}
              className="px-2 py-2 rounded-md hover:bg-muted text-foreground"
            >
              Partner Retailers
            </Link>
            <Link
              href="/#status"
              onClick={() => setMobileMenuOpen(false)}
              className="px-2 py-2 rounded-md hover:bg-muted text-foreground"
            >
              System Health
            </Link>
          </nav>
        </div>
      )}
    </header>
  );
}
