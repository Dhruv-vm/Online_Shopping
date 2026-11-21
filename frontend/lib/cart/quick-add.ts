"use client";

import { useCallback, useRef, useState } from "react";
import { apiClient } from "@/lib/api/client";
import { useCart } from "@/lib/cart/cart-context";

export type QuickAddState = "idle" | "adding" | "added" | "error";

/**
 * Add a product to the cart from a card: resolves the cheapest active, in-stock
 * listing (live from the product API) and uses the existing cart. Ignores clicks
 * while a request is in flight, so a double tap never adds twice.
 */
export function useQuickAdd(slug: string) {
  const { addItem } = useCart();
  const [state, setState] = useState<QuickAddState>("idle");
  const [message, setMessage] = useState<string | null>(null);
  const busy = useRef(false);

  const add = useCallback(async (): Promise<boolean> => {
    if (busy.current) return false;
    busy.current = true;
    setState("adding");
    setMessage(null);
    try {
      const product = await apiClient.getProduct(slug);
      const listing = (product.variants ?? [])
        .flatMap((v) => (v.is_active === false ? [] : v.listings ?? []))
        .filter((l) => l.is_active && l.is_in_stock && l.available_quantity > 0)
        .sort((a, b) => a.selling_price_paise - b.selling_price_paise)[0];
      if (!listing) throw new Error("This product is out of stock.");
      await addItem(listing.id, 1);
      setState("added");
      setTimeout(() => setState((s) => (s === "added" ? "idle" : s)), 1600);
      return true;
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Could not add to cart.");
      setState("error");
      setTimeout(() => setState((s) => (s === "error" ? "idle" : s)), 2600);
      return false;
    } finally {
      busy.current = false;
    }
  }, [slug, addItem]);

  return { state, message, add };
}

/** A small thumbnail flies from the card to the header cart (desktop only). */
export function flyToCart(from: HTMLElement | null) {
  if (!from || typeof window === "undefined") return;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches || window.innerWidth < 640) return;
  const target = document.getElementById("header-cart");
  const img = from.querySelector("img");
  if (!target || !img) return;
  const a = img.getBoundingClientRect();
  const b = target.getBoundingClientRect();
  const ghost = img.cloneNode(true) as HTMLImageElement;
  ghost.removeAttribute("srcset");
  ghost.src = img.currentSrc || img.src;
  Object.assign(ghost.style, {
    position: "fixed", left: `${a.left}px`, top: `${a.top}px`, width: `${a.width}px`, height: `${a.height}px`,
    borderRadius: "16px", objectFit: "cover", zIndex: "60", pointerEvents: "none", opacity: "1",
  });
  document.body.appendChild(ghost);
  const dx = b.left + b.width / 2 - (a.left + a.width / 2);
  const dy = b.top + b.height / 2 - (a.top + a.height / 2);
  const anim = ghost.animate(
    [
      { transform: "translate(0,0) scale(1)", opacity: 1 },
      { transform: `translate(${dx * 0.5}px, ${dy * 0.5 - 60}px) scale(0.45)`, opacity: 0.9, offset: 0.55 },
      { transform: `translate(${dx}px, ${dy}px) scale(0.08)`, opacity: 0.2 },
    ],
    { duration: 650, easing: "cubic-bezier(0.22,1,0.36,1)" },
  );
  anim.onfinish = () => ghost.remove();
  anim.oncancel = () => ghost.remove();
}
