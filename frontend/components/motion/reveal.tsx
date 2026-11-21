"use client";

import { createElement, useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";

/** True once the first-load screen has gone (entrances should play after it). */
export function useLoaderDone() {
  const [done, setDone] = useState(false);
  useEffect(() => {
    if (!document.getElementById("basket-loader")) {
      setDone(true);
      return;
    }
    const on = () => setDone(true);
    document.addEventListener("basket:loaded", on, { once: true });
    const cap = setTimeout(on, 9000); // never block content on a missed event
    return () => {
      document.removeEventListener("basket:loaded", on);
      clearTimeout(cap);
    };
  }, []);
  return done;
}

/**
 * Fades and lifts its content into view once, when it scrolls into the viewport
 * (and not before the first-load screen has finished). Respects reduced motion
 * through the .reveal CSS. Content is always rendered — only its opacity/offset
 * animate — so nothing shifts and nothing is hidden from search or screen readers.
 */
export function Reveal({
  children,
  delay = 0,
  as = "div",
  className = "",
  style,
}: {
  children: ReactNode;
  delay?: number;
  as?: "div" | "section" | "li" | "article";
  className?: string;
  style?: CSSProperties;
}) {
  const ref = useRef<HTMLElement>(null);
  const loaderDone = useLoaderDone();
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    if (!loaderDone || seen || !ref.current) return;
    if (typeof IntersectionObserver === "undefined") {
      setSeen(true);
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setSeen(true);
          io.disconnect();
        }
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.08 },
    );
    io.observe(ref.current);
    return () => io.disconnect();
  }, [loaderDone, seen]);
  return createElement(
    as,
    {
      ref,
      className: `reveal ${seen ? "is-visible" : ""} ${className}`,
      style: { ...style, ["--reveal-delay" as string]: `${delay}ms` },
    },
    children,
  );
}
