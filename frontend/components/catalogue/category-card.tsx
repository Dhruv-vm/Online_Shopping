import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import type { Category } from "@/types";
import {
  Apple,
  BookOpen,
  Dumbbell,
  Home,
  Laptop,
  Shirt,
  Sparkles,
  ShoppingBag,
} from "lucide-react";

const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  Laptop,
  Shirt,
  Apple,
  Sparkles,
  Home,
  Dumbbell,
  BookOpen,
};

interface CategoryCardProps {
  category: Category;
}

export function CategoryCard({ category }: CategoryCardProps) {
  const IconComponent =
    category.icon && ICON_MAP[category.icon]
      ? ICON_MAP[category.icon]
      : ShoppingBag;

  return (
    <Link
      href={`/products?category_slug=${category.slug}`}
      className="group block focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 rounded-xl"
    >
      <Card className="overflow-hidden border transition-all duration-200 group-hover:border-emerald-600/40 group-hover:shadow-md bg-gradient-to-b from-card to-muted/20 h-full">
        <CardContent className="p-3.5 sm:p-4 flex items-center space-x-3 h-full">
          <div className="flex h-10 w-10 sm:h-11 sm:w-11 shrink-0 items-center justify-center rounded-xl bg-emerald-600/10 text-emerald-600 transition-colors group-hover:bg-emerald-600 group-hover:text-white">
            <IconComponent className="h-5 w-5 sm:h-6 sm:w-6 transition-transform duration-200 group-hover:scale-110" />
          </div>
          <div className="space-y-0.5 min-w-0 flex-1">
            <h4 className="font-semibold text-xs sm:text-sm text-foreground group-hover:text-emerald-700 dark:group-hover:text-emerald-400 transition-colors leading-tight line-clamp-2">
              {category.name}
            </h4>
            <p className="text-[11px] sm:text-xs text-muted-foreground">
              {category.product_count} {category.product_count === 1 ? "product" : "products"}
            </p>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
