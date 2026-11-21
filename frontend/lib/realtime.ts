"use client";

/**
 * Live change notices from the backend (`GET /api/v1/realtime/stream`).
 *
 * One EventSource per browser tab, shared by every component. Notices carry
 * only `{type, entity, id, at}` — never data — so components react by
 * refetching through the normal authorised APIs. If the stream is unavailable
 * (signed out, proxy without streaming, network drop) components still
 * refresh on tab focus and on a slow fallback interval.
 */
import { useEffect, useRef, useSyncExternalStore } from "react";

export type LiveNotice = { type: string; entity: string; id: string; at: string };
export type LiveState = "connecting" | "live" | "offline";

type Listener = (n: LiveNotice) => void;

const listeners = new Set<Listener>();
const stateListeners = new Set<() => void>();
let source: EventSource | null = null;
let state: LiveState = "offline";
let retryTimer: ReturnType<typeof setTimeout> | null = null;
let retryDelay = 2000;

function streamUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "");
  const base = configured === "same-origin" ? "" : configured || "http://localhost:8000";
  return `${base}/api/v1/realtime/stream`;
}

function setState(next: LiveState) {
  if (state === next) return;
  state = next;
  stateListeners.forEach((l) => l());
}

function signedIn(): boolean {
  // XSRF-TOKEN is readable and is set/cleared together with the HttpOnly session cookie.
  return typeof document !== "undefined" && /(?:^|;\s*)XSRF-TOKEN=/.test(document.cookie);
}

function open() {
  if (typeof window === "undefined" || source || typeof EventSource === "undefined") return;
  if (!signedIn()) {
    setState("offline"); // signed out: pages still refresh on focus / fallback interval
    return;
  }
  setState("connecting");
  const es = new EventSource(streamUrl(), { withCredentials: true });
  source = es;
  es.addEventListener("ready", () => {
    retryDelay = 2000;
    setState("live");
  });
  es.addEventListener("change", (ev) => {
    try {
      const n = JSON.parse((ev as MessageEvent).data) as LiveNotice;
      listeners.forEach((l) => l(n));
    } catch {
      /* ignore malformed notice */
    }
  });
  es.onerror = () => {
    // Close and retry with backoff (also covers 401 when signed out).
    es.close();
    if (source === es) source = null;
    setState("offline");
    if (listeners.size && !retryTimer) {
      retryTimer = setTimeout(() => {
        retryTimer = null;
        if (listeners.size) open();
      }, retryDelay);
      retryDelay = Math.min(retryDelay * 2, 60000);
    }
  };
}

function close() {
  if (retryTimer) clearTimeout(retryTimer);
  retryTimer = null;
  source?.close();
  source = null;
  setState("offline");
}

/** Re-open the stream immediately (e.g. after sign-in). */
export function reconnectLive() {
  close();
  retryDelay = 2000;
  if (listeners.size) open();
}

function subscribe(l: Listener): () => void {
  listeners.add(l);
  open();
  return () => {
    listeners.delete(l);
    if (!listeners.size) close();
  };
}

/** Current connection state, for a small "Live" indicator. */
export function useLiveState(): LiveState {
  return useSyncExternalStore(
    (cb) => {
      stateListeners.add(cb);
      return () => stateListeners.delete(cb);
    },
    () => state,
    () => "offline",
  );
}

/**
 * Call `onChange` (debounced) whenever a notice whose type starts with one of
 * `prefixes` arrives, when the tab regains focus, and every `fallbackMs` as a
 * safety net. Pass `match` to narrow to one entity id.
 */
export function useLiveUpdates(
  prefixes: string[],
  onChange: () => void,
  opts: { fallbackMs?: number; match?: (n: LiveNotice) => boolean; enabled?: boolean } = {},
) {
  const { fallbackMs = 60000, enabled = true } = opts;
  const cb = useRef(onChange);
  const match = useRef(opts.match);
  cb.current = onChange;
  match.current = opts.match;
  const key = prefixes.join("|");

  useEffect(() => {
    if (!enabled) return;
    const wanted = key.split("|").filter(Boolean);
    let timer: ReturnType<typeof setTimeout> | null = null;
    const fire = () => {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        timer = null;
        cb.current();
      }, 250);
    };
    const unsub = subscribe((n) => {
      if (!wanted.some((p) => n.type.startsWith(p))) return;
      if (match.current && !match.current(n)) return;
      fire();
    });
    const onVisible = () => {
      if (document.visibilityState === "visible") fire();
    };
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("focus", onVisible);
    const fallback = fallbackMs > 0 ? setInterval(() => {
      if (document.visibilityState === "visible") cb.current();
    }, fallbackMs) : null;
    return () => {
      unsub();
      if (timer) clearTimeout(timer);
      if (fallback) clearInterval(fallback);
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("focus", onVisible);
    };
  }, [key, fallbackMs, enabled]);
}
