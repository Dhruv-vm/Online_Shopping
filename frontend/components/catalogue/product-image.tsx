"use client";

import { useState } from "react";
import { ShoppingBasket } from "lucide-react";

const UNSPLASH_WIDTHS = [240, 360, 480, 640, 828, 1080];

/** Responsive Unsplash URL: Unsplash resizes on the fly and, with auto=format,
 * serves AVIF or WebP to browsers that accept them. */
function unsplash(src: string, w: number) {
  const u = new URL(src);
  u.searchParams.set("w", String(w));
  u.searchParams.set("auto", "format");
  u.searchParams.set("fit", u.searchParams.get("fit") || "crop");
  u.searchParams.set("q", "75");
  return u.toString();
}

/**
 * Product photo with consistent cropping, responsive sizes, lazy loading below the
 * fold and a neutral fallback when the URL is missing or fails (never a broken
 * image). The parent sets the aspect ratio, so nothing shifts while it loads.
 */
export function ProductImage({
  src,
  alt,
  className = "",
  sizes = "(min-width: 1280px) 20vw, (min-width: 1024px) 25vw, (min-width: 640px) 33vw, 50vw",
  eager = false,
  fit = "cover",
}: {
  src?: string | null;
  alt: string;
  className?: string;
  sizes?: string;
  eager?: boolean;
  fit?: "cover" | "contain";
}) {
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);
  if (!src || failed) {
    return (
      <div className={`flex h-full w-full items-center justify-center bg-cream text-ink/25 ${className}`} role="img" aria-label={alt}>
        <ShoppingBasket className="h-10 w-10" aria-hidden />
      </div>
    );
  }
  const isUnsplash = src.includes("images.unsplash.com");
  let srcSet: string | undefined;
  let main = src;
  try {
    if (isUnsplash) {
      srcSet = UNSPLASH_WIDTHS.map((w) => `${unsplash(src, w)} ${w}w`).join(", ");
      main = unsplash(src, 640);
    }
  } catch {
    srcSet = undefined;
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element -- remote catalogue/media URLs with explicit srcset/sizes
    <img
      src={main}
      srcSet={srcSet}
      sizes={srcSet ? sizes : undefined}
      alt={alt}
      loading={eager ? "eager" : "lazy"}
      fetchPriority={eager ? "high" : undefined}
      decoding="async"
      onLoad={() => setLoaded(true)}
      onError={() => setFailed(true)}
      className={`h-full w-full ${fit === "contain" ? "object-contain" : "object-cover"} object-center transition-[opacity,transform] duration-slow ease-out ${loaded ? "opacity-100" : "opacity-0"} ${className}`}
    />
  );
}
