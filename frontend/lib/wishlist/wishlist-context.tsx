"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

/**
 * Wishlist saved on this device (browser storage), like the compare list.
 * Basket has no wishlist API yet, so nothing is sent to the server and
 * nothing needs sign-in; the /wishlist page loads live product data by slug.
 */
interface WishlistContextType {
  slugs: string[];
  count: number;
  has: (slug: string) => boolean;
  toggle: (slug: string) => boolean; // returns the new "saved" state
  remove: (slug: string) => void;
}

const WishlistContext = createContext<WishlistContextType | undefined>(undefined);
const STORAGE_KEY = "basket_wishlist_slugs";
const MAX_ITEMS = 100;

export function WishlistProvider({ children }: { children: React.ReactNode }) {
  const [slugs, setSlugs] = useState<string[]>([]);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    try {
      const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
      if (Array.isArray(parsed)) setSlugs(parsed.filter((s) => typeof s === "string").slice(0, MAX_ITEMS));
    } catch {
      /* storage unavailable or corrupted */
    } finally {
      setReady(true);
    }
    // Keep tabs in sync.
    const onStorage = (e: StorageEvent) => {
      if (e.key !== STORAGE_KEY) return;
      try {
        const v = JSON.parse(e.newValue || "[]");
        if (Array.isArray(v)) setSlugs(v);
      } catch {
        /* ignore */
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  useEffect(() => {
    if (!ready) return;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(slugs));
    } catch {
      /* quota */
    }
  }, [slugs, ready]);

  const has = useCallback((slug: string) => slugs.includes(slug), [slugs]);
  const toggle = useCallback(
    (slug: string) => {
      const saved = !slugs.includes(slug);
      setSlugs((prev) => (prev.includes(slug) ? prev.filter((s) => s !== slug) : [slug, ...prev].slice(0, MAX_ITEMS)));
      return saved;
    },
    [slugs],
  );
  const remove = useCallback((slug: string) => setSlugs((prev) => prev.filter((s) => s !== slug)), []);

  const value = useMemo(() => ({ slugs, count: slugs.length, has, toggle, remove }), [slugs, has, toggle, remove]);
  return <WishlistContext.Provider value={value}>{children}</WishlistContext.Provider>;
}

export function useWishlist(): WishlistContextType {
  const ctx = useContext(WishlistContext);
  if (!ctx) throw new Error("useWishlist must be used within WishlistProvider");
  return ctx;
}
