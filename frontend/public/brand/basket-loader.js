/* ==========================================================================
   Basket loading screen controller
   - Shows while the page (and anything registered via BasketLoader.track) loads
   - Progress creeps smoothly toward 90% while waiting, then completes to 100%
   - Stays up for at least MIN_VISIBLE (default 2.5 s, data-min-visible) so the
     animation is always seen; it never delays the app itself, only hiding
   - Fades out cleanly, removes itself, and fires a `basket:loaded` event

   Public API (window.BasketLoader):
     track(promise)  keep the loader up until this promise settles
     done()          mark the app ready (only needed with data-manual)
   Testing: append ?loaderDemo=4000 to simulate a 4 s load.
   ========================================================================== */
(function () {
  "use strict";

  var root = document.getElementById("basket-loader");
  if (!root) return;

  var html = document.documentElement;
  var fill = root.querySelector(".bl-bar-fill");
  var bar = root.querySelector(".bl-bar");
  var sr = root.querySelector(".bl-sr");

  // Minimum time the animation stays on screen, measured from when it first
  // renders. This only delays *hiding* the loader; nothing else waits on it.
  var MIN_VISIBLE = Number(root.dataset.minVisible || 2500); // ms
  var HOLD_AT_FULL = 150; // ms at 100% so completion reads before the fade
  var GLIDE_LEAD = 250;   // bar's time curve finishes this early to absorb smoothing lag
  var FADE_MS = 420;
  var manual = root.hasAttribute("data-manual");

  var startedAt = performance.now();
  var pending = 0;
  var pageLoaded = document.readyState === "complete";
  var manualDone = !manual;
  var appReady = false; // condition 1: app/page genuinely ready
  var finished = false;

  var progress = 0;
  var lastFrame = startedAt;
  var lastAria = -1;

  function minElapsed(now) { // condition 2: minimum display time reached
    return now - startedAt >= MIN_VISIBLE;
  }

  // Loader hides only when BOTH are true:
  //   shouldShowLoader = !appReady || !minElapsed
  function shouldShowLoader(now) {
    return !appReady || !minElapsed(now);
  }

  function check() {
    if (!appReady && pageLoaded && manualDone && pending === 0) appReady = true;
  }

  function track(promise) {
    pending++;
    Promise.resolve(promise).then(release, release);
    return promise;
  }

  function release() {
    pending = Math.max(0, pending - 1);
    check();
  }

  function setProgress(p) {
    progress = p;
    fill.style.transform = "translate3d(" + ((p - 1) * 100).toFixed(3) + "%,0,0)";
    var pct = Math.floor(p * 100 + 1e-6); // only reads 100 when truly done
    if (pct !== lastAria) {
      lastAria = pct;
      bar.setAttribute("aria-valuenow", String(pct));
    }
  }

  function smoothstep(x) {
    x = Math.min(1, Math.max(0, x));
    return x * x * (3 - 2 * x);
  }

  // Bar target:
  //  - not ready: asymptotic creep toward 90% (never claims done)
  //  - ready but minimum not reached: glide so it reaches 100% just as MIN_VISIBLE ends
  //  - ready and minimum reached: finish to 100%
  // The bar never moves backwards and never sits frozen at 100%.
  function targetFor(now) {
    var t = now - startedAt;
    var creep = 0.9 * (1 - Math.exp(-t / 2400));
    if (!appReady) return creep;
    if (!minElapsed(now)) return Math.max(creep, smoothstep(t / Math.max(1, MIN_VISIBLE - GLIDE_LEAD)));
    return 1;
  }

  // Closing phase (both conditions met) is time-based, not frame-based, so the
  // hide happens on schedule even if the browser delivers frames slowly.
  var closeAt = 0, closeFrom = 0, closeMs = 0;

  function frame(now) {
    if (finished) return;
    var dt = Math.min(100, now - lastFrame) / 1000;
    lastFrame = now;

    if (shouldShowLoader(now)) {
      // Waiting: frame-rate independent smoothing toward the target
      var target = targetFor(now);
      var rate = appReady ? 14 : 3.2;
      var next = progress + (target - progress) * (1 - Math.exp(-dt * rate));
      setProgress(Math.min(0.985, Math.max(progress, next)));
    } else {
      // Ready + minimum reached: ease the remainder to 100% over a short,
      // proportional duration, hold briefly, then hide.
      if (!closeAt) {
        closeAt = now;
        closeFrom = progress;
        closeMs = Math.max(100, 600 * (1 - closeFrom));
      }
      var k = Math.min(1, (now - closeAt) / closeMs);
      var eased = 1 - Math.pow(1 - k, 3);
      setProgress(k === 1 ? 1 : closeFrom + (1 - closeFrom) * eased);
      if (now - closeAt >= closeMs + HOLD_AT_FULL) return end();
    }
    requestAnimationFrame(frame);
  }

  function end() {
    if (finished) return;
    finished = true;
    clearInterval(watchdog);
    setProgress(1);
    finish();
  }

  // Watchdog: hidden/throttled windows may deliver few or no frames. Still
  // honour both conditions, then finish on time without relying on rAF.
  var readySince = 0;
  var watchdog = setInterval(function () {
    var now = performance.now();
    if (finished) return;
    if (shouldShowLoader(now)) { readySince = 0; return; }
    if (!readySince) readySince = now;
    if (now - readySince > 600 + HOLD_AT_FULL + 150) end();
  }, 100);

  function finish() {
    if (sr) sr.textContent = "Ready";
    html.classList.remove("bl-is-loading");
    root.classList.add("is-done");
    var shownMs = Math.round(performance.now() - startedAt);
    window.BasketLoader.shownMs = shownMs;
    document.dispatchEvent(new CustomEvent("basket:loaded", { detail: { shownMs: shownMs } }));
    setTimeout(function () {
      if (root.parentNode) root.parentNode.removeChild(root);
    }, FADE_MS + 60);
  }

  window.addEventListener("load", function () {
    pageLoaded = true;
    check();
  }, { once: true });

  // Images already hold the window `load` event; fonts are the other blocker.
  // Capped so a font that never settles can't hold the loader hostage.
  if (document.fonts && document.fonts.ready) {
    track(Promise.race([
      document.fonts.ready,
      new Promise(function (r) { setTimeout(r, 3000); })
    ]));
  }

  var demo = Number(new URLSearchParams(location.search).get("loaderDemo"));
  if (demo > 0) {
    track(new Promise(function (r) { setTimeout(r, demo); }));
  }

  window.BasketLoader = {
    track: track,
    done: function () { manualDone = true; check(); }
  };

  check();
  requestAnimationFrame(frame);
})();
