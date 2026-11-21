import Link from "next/link";
import { ShoppingBasket } from "lucide-react";

/** The existing BASKET mark (green tile + basket glyph) and wordmark. */
export function BasketLogo({
  tagline,
  href = "/",
  inverted = false,
}: {
  tagline?: string;
  href?: string;
  inverted?: boolean;
}) {
  return (
    <Link href={href} className="flex items-center gap-2.5 shrink-0" aria-label="BASKET home">
      <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand text-white shadow-sm">
        <ShoppingBasket className="h-5 w-5" aria-hidden />
      </span>
      <span className="flex flex-col leading-none">
        <span className={`text-xl font-extrabold tracking-tight ${inverted ? "text-white" : "text-charcoal"}`}>
          BASKET
        </span>
        {tagline && (
          <span className={`mt-0.5 hidden text-[10px] sm:block ${inverted ? "text-white/70" : "text-muted-foreground"}`}>
            {tagline}
          </span>
        )}
      </span>
    </Link>
  );
}
