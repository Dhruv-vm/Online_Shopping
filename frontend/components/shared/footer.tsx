import Link from "next/link";
import { ShoppingBasket } from "lucide-react";

export function Footer() {
  return (
    <footer className="w-full border-t bg-muted/20 py-10 text-xs text-muted-foreground mt-16">
      <div className="container mx-auto px-4 sm:px-6 space-y-6">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center space-x-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-emerald-600 text-white">
              <ShoppingBasket className="h-4 w-4" />
            </div>
            <span className="font-bold text-sm text-foreground">BASKET</span>
            <span className="text-[11px] text-muted-foreground">— Multi-Category Indian Retail Platform</span>
          </div>

          <div className="flex items-center space-x-6 text-xs font-medium">
            <Link href="/products" className="hover:text-foreground transition-colors">
              Catalogue
            </Link>
            <Link href="/categories" className="hover:text-foreground transition-colors">
              Categories
            </Link>
            <Link href="/retailers" className="hover:text-foreground transition-colors">
              Retailers
            </Link>
            <Link href="/#status" className="hover:text-foreground transition-colors">
              System Health
            </Link>
          </div>
        </div>

        <div className="border-t pt-4 flex flex-col sm:flex-row items-center justify-between text-[11px] text-muted-foreground gap-2">
          <p>
            Phase 1 Catalogue & Storefront Foundation • PostgreSQL Source of Truth • Strict API Contracts
          </p>
          <p>
            Designed for two-developer engineering workflow in Google Antigravity.
          </p>
        </div>
      </div>
    </footer>
  );
}
