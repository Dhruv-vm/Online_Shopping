"use client";

import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { LOADER_INNER_HTML } from "./loader-markup";

const MIN_VISIBLE_MS = 800; // brief: ~800–1000 ms per navigation
const MAX_VISIBLE_MS = 10000; // never stuck: hide even if a navigation never settles
const FADE_MS = 420; // matches .bl transition in the Hack UI CSS

/**
 * Route-transition screen: the same Hack UI loader (markup + CSS), shown only for
 * real page navigations — a link to another path, or browser back/forward. Query
 * changes (filters, sorting, search params), dropdowns and cart actions never show
 * it. The progress bar follows the Hack UI controller: it creeps toward 90% while
 * the next page loads and completes once the page is ready and the minimum time
 * has passed.
 */
export function RouteLoader() {
  const pathname = usePathname();
  const [phase, setPhase] = useState<"idle" | "loading" | "closing">("idle");
  const startedAt = useRef(0);
  const navDone = useRef(false);
  const fromPath = useRef("");
  const rootRef = useRef<HTMLDivElement>(null);
  const raf = useRef(0);

  const setBar = (p: number) => {
    const root = rootRef.current;
    const fill = root?.querySelector<HTMLElement>(".bl-bar-fill");
    if (fill) fill.style.transform = `translate3d(${((p - 1) * 100).toFixed(3)}%,0,0)`;
    root?.querySelector(".bl-bar")?.setAttribute("aria-valuenow", String(Math.floor(p * 100)));
  };

  const phaseRef = useRef(phase);
  phaseRef.current = phase;
  const renderedPath = useRef(pathname); // last path React rendered

  /** Show the screen for a navigation away from `prevPath`. */
  const start = useCallback((prevPath: string) => {
    // The first-load screen is still up, or a transition is already running.
    if (document.getElementById("basket-loader") || phaseRef.current !== "idle") return;
    startedAt.current = performance.now();
    navDone.current = false;
    fromPath.current = prevPath;
    setPhase("loading");
  }, []);

  // Which navigations show the screen: same-origin links to a different path.
  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const a = (e.target as Element | null)?.closest?.("a");
      if (!a || !a.href || a.target === "_blank" || a.hasAttribute("download")) return;
      if (a.getAttribute("href")?.startsWith("#")) return;
      let url: URL;
      try {
        url = new URL(a.href, window.location.href);
      } catch {
        return;
      }
      if (url.origin !== window.location.origin) return;
      if (url.pathname === window.location.pathname) return; // same page (query/hash only)
      start(window.location.pathname);
    };
    const onPop = () => {
      // Back/forward: the URL has already changed; React has not rendered it yet.
      if (window.location.pathname !== renderedPath.current) start(renderedPath.current);
    };
    document.addEventListener("click", onClick, true);
    window.addEventListener("popstate", onPop);
    return () => {
      document.removeEventListener("click", onClick, true);
      window.removeEventListener("popstate", onPop);
    };
  }, [start]);

  // The new route rendered: the navigation is done.
  useEffect(() => {
    renderedPath.current = pathname;
    if (phaseRef.current === "loading" && pathname !== fromPath.current) navDone.current = true;
  }, [pathname]);

  // Progress + close, following the Hack UI controller's rules.
  useEffect(() => {
    if (phase !== "loading") return;
    document.documentElement.classList.add("bl-is-loading");
    let progress = 0;
    let last = performance.now();
    const frame = (now: number) => {
      const t = now - startedAt.current;
      const dt = Math.min(100, now - last) / 1000;
      last = now;
      const ready = navDone.current && t >= MIN_VISIBLE_MS;
      if (ready || t >= MAX_VISIBLE_MS) {
        setBar(1);
        setPhase("closing");
        return;
      }
      const creep = 0.9 * (1 - Math.exp(-t / 2400));
      const target = navDone.current ? Math.max(creep, t / MIN_VISIBLE_MS) : creep;
      progress = Math.min(0.985, Math.max(progress, progress + (target - progress) * (1 - Math.exp(-dt * (navDone.current ? 14 : 3.2)))));
      setBar(progress);
      raf.current = requestAnimationFrame(frame);
    };
    raf.current = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf.current);
  }, [phase]);

  useEffect(() => {
    if (phase !== "closing") return;
    document.documentElement.classList.remove("bl-is-loading");
    const id = setTimeout(() => setPhase("idle"), FADE_MS + 60);
    return () => clearTimeout(id);
  }, [phase]);

  if (phase === "idle") return null;
  return (
    <div
      ref={rootRef}
      className={`bl${phase === "closing" ? " is-done" : ""}`}
      role="status"
      aria-label="Loading page"
      dangerouslySetInnerHTML={{ __html: LOADER_INNER_HTML }}
    />
  );
}
