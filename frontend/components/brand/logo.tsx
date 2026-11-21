import Link from "next/link";

/**
 * The official Basket logo (white wordmark, yellow cart "e", green/yellow wheels)
 * from the Hack UI brand kit. It is designed for dark backgrounds; on light
 * backgrounds it sits on a black tile so the mark is never altered.
 */
export function BasketLogo({
  href = "/",
  height = 30,
  onLight = false,
  className = "",
  priority = false,
}: {
  href?: string;
  height?: number;
  onLight?: boolean;
  className?: string;
  priority?: boolean;
  /** @deprecated kept for older call sites; the official logo has no tagline */
  tagline?: string;
  /** @deprecated the official logo is always light-on-dark */
  inverted?: boolean;
}) {
  const width = Math.round((height * 491) / 134);
  const img = (
    <picture>
      <source srcSet="/brand/basket-logo-68.webp 1x, /brand/basket-logo.webp 2x" type="image/webp" />
      {/* eslint-disable-next-line @next/next/no-img-element -- static brand asset with explicit size */}
      <img
        src="/brand/basket-logo-68.png"
        width={width}
        height={height}
        alt="Basket"
        decoding="async"
        fetchPriority={priority ? "high" : undefined}
        className="block h-auto select-none"
        style={{ width, height }}
        draggable={false}
      />
    </picture>
  );
  return (
    <Link
      href={href}
      aria-label="Basket home"
      className={`group inline-flex shrink-0 items-center transition-transform duration-base ease-out hover:-translate-y-px ${onLight ? "rounded-xl bg-ink px-3 py-2" : ""} ${className}`}
    >
      {img}
    </Link>
  );
}

/** The cart mark on its own (for compact placements). */
export function BasketMark({ size = 28 }: { size?: number }) {
  return (
    // eslint-disable-next-line @next/next/no-img-element -- static brand asset
    <img src="/brand/cart-body.webp" width={size} height={Math.round((size * 241) / 311)} alt="" aria-hidden className="select-none" />
  );
}
