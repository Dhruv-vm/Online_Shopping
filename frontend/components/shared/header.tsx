import Link from "next/link";
import { ShoppingBasket } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export function Header() {
  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto flex h-16 items-center justify-between px-4 sm:px-6">
        <Link href="/" className="flex items-center space-x-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-600 text-white shadow-sm">
            <ShoppingBasket className="h-5 w-5" />
          </div>
          <span className="text-xl font-bold tracking-tight text-foreground">
            BASKET
          </span>
          <Badge variant="outline" className="ml-2 font-mono text-[10px]">
            Phase 0
          </Badge>
        </Link>

        <nav className="flex items-center space-x-6 text-sm font-medium">
          <Link
            href="#architecture"
            className="text-muted-foreground transition-colors hover:text-foreground"
          >
            Architecture
          </Link>
          <Link
            href="#stack"
            className="text-muted-foreground transition-colors hover:text-foreground"
          >
            Stack
          </Link>
          <Link
            href="#status"
            className="text-muted-foreground transition-colors hover:text-foreground"
          >
            System Status
          </Link>
        </nav>
      </div>
    </header>
  );
}
