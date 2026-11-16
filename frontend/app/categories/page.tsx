import Link from "next/link";
import { CategoryCard } from "@/components/catalogue/category-card";
import { Badge } from "@/components/ui/badge";
import { apiClient } from "@/lib/api/client";
import type { Category } from "@/types";
import { LayoutGrid } from "lucide-react";

export const revalidate = 0;

export default async function CategoriesPage() {
  let categories: Category[] = [];
  try {
    categories = await apiClient.getCategories();
  } catch (err) {
    console.error("Failed to load categories:", err);
  }

  return (
    <div className="container mx-auto px-4 py-10 sm:px-6 space-y-8">
      <div className="space-y-2 border-b pb-6">
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-xs text-emerald-600 border-emerald-600/30">
            Departments
          </Badge>
          <span className="text-xs text-muted-foreground">Universal Retail Taxonomy</span>
        </div>
        <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">
          Browse by Category
        </h1>
        <p className="text-sm text-muted-foreground max-w-2xl">
          Explore products organized across {categories.length} verified departments, backed by authoritative stock in PostgreSQL.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
        {categories.map((cat) => (
          <div key={cat.id} className="space-y-2">
            <CategoryCard category={cat} />
            {cat.description && (
              <p className="text-xs text-muted-foreground line-clamp-2 px-1">
                {cat.description}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
