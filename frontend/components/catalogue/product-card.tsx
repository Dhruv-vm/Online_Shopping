import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { formatPrice } from "@/lib/utils";
import type { ProductSummary } from "@/types";
import { Store, Tag } from "lucide-react";

interface ProductCardProps {
  product: ProductSummary;
}

export function ProductCard({ product }: ProductCardProps) {
  const discountPercent =
    product.original_price_paise &&
    product.original_price_paise > product.min_price_paise
      ? Math.round(
          ((product.original_price_paise - product.min_price_paise) /
            product.original_price_paise) *
            100
        )
      : 0;

  return (
    <Card className="group relative flex flex-col overflow-hidden transition-all duration-200 hover:shadow-lg hover:-translate-y-0.5 border-border/80">
      <Link
        href={`/products/${product.slug}`}
        className="flex flex-col h-full focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 rounded-lg"
      >
        {/* Product Image Area */}
        <div className="relative aspect-square w-full overflow-hidden bg-muted/30">
          {product.primary_image ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={product.primary_image}
              alt={product.name}
              className="h-full w-full object-cover object-center transition-transform duration-300 group-hover:scale-105"
              loading="lazy"
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center bg-muted text-muted-foreground">
              <Tag className="h-12 w-12 stroke-1" />
            </div>
          )}

          {/* Badges Overlay */}
          <div className="absolute top-2.5 left-2.5 flex flex-col gap-1.5 items-start">
            {discountPercent > 0 && (
              <Badge className="bg-rose-600 text-white hover:bg-rose-700 shadow-sm text-xs font-bold">
                {discountPercent}% OFF
              </Badge>
            )}
            {!product.is_in_stock && (
              <Badge variant="outline" className="bg-background/90 text-destructive border-destructive/40 text-xs">
                Out of Stock
              </Badge>
            )}
          </div>

          <div className="absolute top-2.5 right-2.5">
            <Badge variant="secondary" className="text-[11px] bg-background/85 backdrop-blur-sm shadow-xs border">
              {product.category_name}
            </Badge>
          </div>
        </div>

        {/* Product Details Content */}
        <CardContent className="flex flex-1 flex-col p-4 justify-between">
          <div className="space-y-1.5">
            <p className="text-xs font-semibold tracking-wider uppercase text-muted-foreground">
              {product.brand}
            </p>
            <h3 className="font-semibold text-sm line-clamp-2 leading-snug text-foreground group-hover:text-emerald-700 dark:group-hover:text-emerald-400 transition-colors">
              {product.name}
            </h3>
          </div>

          <div className="pt-3 border-t border-border/50 mt-3 space-y-2">
            {/* Price Display */}
            <div className="flex items-baseline gap-2">
              {product.min_price_paise > 0 ? (
                <>
                  <span className="text-lg font-bold text-foreground">
                    {formatPrice(product.min_price_paise, product.currency)}
                  </span>
                  {product.original_price_paise &&
                    product.original_price_paise > product.min_price_paise && (
                      <span className="text-xs text-muted-foreground line-through">
                        {formatPrice(product.original_price_paise, product.currency)}
                      </span>
                    )}
                </>
              ) : (
                <span className="text-sm font-medium text-muted-foreground">
                  Currently Unavailable
                </span>
              )}
            </div>

            {/* Seller and Variant Metadata */}
            <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-1">
              <span className="flex items-center gap-1">
                <Store className="h-3 w-3 text-emerald-600" />
                {product.retailer_count} {product.retailer_count === 1 ? "seller" : "sellers"}
              </span>
              <span>
                {product.variant_count} {product.variant_count === 1 ? "option" : "options"}
              </span>
            </div>
          </div>
        </CardContent>
      </Link>
    </Card>
  );
}
