"use client";

import { useState } from "react";
import { ShoppingBasket } from "lucide-react";

/**
 * Product photo with consistent cropping, lazy loading and a neutral fallback
 * when the URL is missing or fails to load (never a broken-image icon).
 */
export function ProductImage({
  src,
  alt,
  className = "",
  sizes = "(min-width: 1024px) 25vw, (min-width: 640px) 50vw, 100vw",
  eager = false,
}: {
  src?: string | null;
  alt: string;
  className?: string;
  sizes?: string;
  eager?: boolean;
}) {
  const [failed, setFailed] = useState(false);
  if (!src || failed) {
    return (
      <div className={`flex h-full w-full items-center justify-center bg-gradient-to-br from-brand-light to-surface text-brand/50 ${className}`} role="img" aria-label={alt}>
        <ShoppingBasket className="h-10 w-10" aria-hidden />
      </div>
    );
  }
  // Unsplash supports on-the-fly resizing; request a size suited to cards.
  const optimised = src.includes("images.unsplash.com") ? src.replace(/([?&])w=\d+/, "$1w=600") : src;
  return (
    // eslint-disable-next-line @next/next/no-img-element -- remote catalogue/media URLs; sizes set explicitly
    <img
      src={optimised}
      alt={alt}
      sizes={sizes}
      loading={eager ? "eager" : "lazy"}
      decoding="async"
      onError={() => setFailed(true)}
      className={`h-full w-full object-cover object-center ${className}`}
    />
  );
}
