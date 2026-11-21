import { LOADER_INNER_HTML } from "./loader-markup";

/** Minimum time the first-load screen stays up (brief: ~800–1000 ms). */
const MIN_VISIBLE_MS = 1000;
/** Never keep the screen up longer than this, even if the app fails to signal ready. */
const SAFETY_CAP_MS = 8000;

/**
 * Never-stuck guarantee. The Hack UI controller closes only after window "load",
 * which a hanging request (image, font, third-party) can delay indefinitely.
 * At the cap we mark the app ready and, if the loader is still up shortly after,
 * close it the same way the controller does (class swap, event, fade, removal).
 */
const SAFETY_SCRIPT = `setTimeout(function(){
  var B=window.BasketLoader; if(B) B.done();
  setTimeout(function(){
    var root=document.getElementById("basket-loader"); if(!root||root.classList.contains("is-done")) return;
    document.documentElement.classList.remove("bl-is-loading");
    root.classList.add("is-done");
    document.dispatchEvent(new CustomEvent("basket:loaded",{detail:{forced:true}}));
    setTimeout(function(){ if(root.parentNode) root.parentNode.removeChild(root); }, 480);
  }, 1200);
},${SAFETY_CAP_MS});`;

/**
 * First-load screen: the Hack UI loader, server-rendered as the first thing in
 * <body> so it covers the page before anything else paints. The unchanged Hack UI
 * controller (/brand/basket-loader.js) runs right after the markup, exactly as in
 * the kit. `data-manual` makes it wait for <LoaderReady/> (React hydrated) as
 * well as window load + fonts; a safety timer guarantees it can never stick.
 * The markup lives inside dangerouslySetInnerHTML because the controller removes
 * its own node when done — React never reconciles those children.
 */
export function InitialLoader() {
  const html = `<div id="basket-loader" class="bl" role="status" aria-label="Loading Basket" data-min-visible="${MIN_VISIBLE_MS}" data-manual>${LOADER_INNER_HTML}</div>`;
  return (
    <>
      <div suppressHydrationWarning dangerouslySetInnerHTML={{ __html: html }} />
      {/* eslint-disable-next-line @next/next/no-sync-scripts -- must run synchronously right after the markup, before first paint completes */}
      <script src="/brand/basket-loader.js" />
      <script
        dangerouslySetInnerHTML={{
          __html: SAFETY_SCRIPT,
        }}
      />
    </>
  );
}

/** Runs before first paint: the loader CSS keys off this class (no scroll, black backdrop). */
export const LOADING_CLASS_SCRIPT = `document.documentElement.classList.add("bl-is-loading");`;
