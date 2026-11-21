"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { Category, Retailer } from "@/types";
import { Check, FilterX } from "lucide-react";

interface ProductFiltersProps {
  categories: Category[];
  retailers: Retailer[];
  selectedCategory: string;
  selectedRetailer: string;
  minPrice: string;
  maxPrice: string;
  inStockOnly: boolean;
  onCategoryChange: (catSlug: string) => void;
  onRetailerChange: (retId: string) => void;
  onMinPriceChange: (val: string) => void;
  onMaxPriceChange: (val: string) => void;
  onInStockToggle: () => void;
  onClearFilters: () => void;
}

export function ProductFilters({
  categories,
  retailers,
  selectedCategory,
  selectedRetailer,
  minPrice,
  maxPrice,
  inStockOnly,
  onCategoryChange,
  onRetailerChange,
  onMinPriceChange,
  onMaxPriceChange,
  onInStockToggle,
  onClearFilters,
}: ProductFiltersProps) {
  const hasActiveFilters = Boolean(
    selectedCategory ||
      selectedRetailer ||
      minPrice ||
      maxPrice ||
      inStockOnly
  );

  return (
    <div className="space-y-6 text-sm">
      <div className="flex items-center justify-between pb-3 border-b">
        <h3 className="font-bold text-base text-foreground">Filters</h3>
        {hasActiveFilters && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onClearFilters}
            className="h-8 px-2 text-xs text-muted-foreground hover:text-destructive"
          >
            <FilterX className="h-3.5 w-3.5 mr-1" />
            Clear all
          </Button>
        )}
      </div>

      {/* Categories Filter */}
      <div className="space-y-2.5">
        <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Categories
        </label>
        <div className="flex flex-col space-y-1">
          <button
            type="button"
            onClick={() => onCategoryChange("")}
            className={`flex items-center justify-between px-2.5 py-1.5 rounded-md text-left text-xs font-medium transition-colors ${
              !selectedCategory
                ? "bg-brand-yellow/35 text-ink font-semibold"
                : "text-muted-foreground hover:bg-muted"
            }`}
          >
            <span>All Categories</span>
            {!selectedCategory && <Check className="h-3.5 w-3.5" />}
          </button>
          {categories.map((cat) => {
            const isSelected = selectedCategory === cat.slug;
            return (
              <button
                key={cat.id}
                type="button"
                onClick={() => onCategoryChange(isSelected ? "" : cat.slug)}
                className={`flex items-center justify-between px-2.5 py-1.5 rounded-md text-left text-xs font-medium transition-colors ${
                  isSelected
                    ? "bg-brand-yellow/35 text-ink font-semibold"
                    : "text-muted-foreground hover:bg-muted"
                }`}
              >
                <span className="truncate">{cat.name}</span>
                <span className="text-[10px] text-muted-foreground ml-2">
                  ({cat.product_count})
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Retailers Filter */}
      <div className="space-y-2.5 pt-3 border-t">
        <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Retail Partners
        </label>
        <div className="flex flex-col space-y-1 max-h-48 overflow-y-auto pr-1">
          <button
            type="button"
            onClick={() => onRetailerChange("")}
            className={`flex items-center justify-between px-2.5 py-1.5 rounded-md text-left text-xs font-medium transition-colors ${
              !selectedRetailer
                ? "bg-brand-yellow/35 text-ink font-semibold"
                : "text-muted-foreground hover:bg-muted"
            }`}
          >
            <span>All Retailers</span>
            {!selectedRetailer && <Check className="h-3.5 w-3.5" />}
          </button>
          {retailers.map((ret) => {
            const isSelected = selectedRetailer === ret.id;
            return (
              <button
                key={ret.id}
                type="button"
                onClick={() => onRetailerChange(isSelected ? "" : ret.id)}
                className={`flex items-center justify-between px-2.5 py-1.5 rounded-md text-left text-xs font-medium transition-colors ${
                  isSelected
                    ? "bg-brand-yellow/35 text-ink font-semibold"
                    : "text-muted-foreground hover:bg-muted"
                }`}
              >
                <span className="truncate">{ret.name}</span>
                {isSelected && <Check className="h-3.5 w-3.5 shrink-0 ml-1 text-emerald-600" />}
              </button>
            );
          })}
        </div>
      </div>

      {/* Price Range Filter */}
      <div className="space-y-2.5 pt-3 border-t">
        <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Price (₹)
        </label>
        <div className="grid grid-cols-2 gap-2">
          <Input
            type="number"
            placeholder="Min ₹"
            value={minPrice}
            onChange={(e) => onMinPriceChange(e.target.value)}
            className="h-8 text-xs"
            min="0"
          />
          <Input
            type="number"
            placeholder="Max ₹"
            value={maxPrice}
            onChange={(e) => onMaxPriceChange(e.target.value)}
            className="h-8 text-xs"
            min="0"
          />
        </div>
      </div>

      {/* Availability Filter */}
      <div className="pt-3 border-t">
        <label className="flex items-center space-x-2.5 cursor-pointer">
          <input
            type="checkbox"
            checked={inStockOnly}
            onChange={onInStockToggle}
            className="h-4 w-4 rounded border-gray-300 text-emerald-600 focus:ring-emerald-500"
          />
          <span className="text-xs font-medium text-foreground">
            In Stock Only
          </span>
        </label>
      </div>
    </div>
  );
}
