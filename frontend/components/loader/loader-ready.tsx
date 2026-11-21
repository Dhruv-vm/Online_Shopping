"use client";

import { useEffect } from "react";

declare global {
  interface Window {
    BasketLoader?: { done: () => void; track: (p: Promise<unknown>) => Promise<unknown>; shownMs?: number };
  }
}

/** Tells the first-load screen the app has hydrated (its "manual" ready signal). */
export function LoaderReady() {
  useEffect(() => {
    window.BasketLoader?.done();
  }, []);
  return null;
}
