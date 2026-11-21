// The Basket loading screen markup, verbatim from "Hack UI/index.html"
// (only the asset paths point at /brand/*.webp — the same artwork, optimised).
// Shared by the first-load screen and the route-transition overlay so both are
// exactly the Hack UI loader.
export const LOADER_INNER_HTML = `
    <div class="bl-inner">
      <img class="bl-logo" src="/brand/basket-logo.webp" width="491" height="134" alt="Basket" decoding="async">

      <div class="bl-scene" aria-hidden="true">
        <div class="bl-cart">
          <div class="bl-cart-top">
            <div class="bl-products">
              <div class="bl-prod bl-prod--apple"><div class="bl-prod-y">
                <svg viewBox="0 0 48 48"><path fill="#E53935" d="M24 15c-3-2.6-9.5-3.6-13.4.6C6.7 19.8 6.4 27 9.2 33.6c2.8 6.4 7.6 10.6 11.6 9.6 1.4-.4 2.2-1 3.2-1s1.8.6 3.2 1c4 1 8.8-3.2 11.6-9.6 2.8-6.6 2.5-13.8-1.4-18C33.5 11.4 27 12.4 24 15z"/><ellipse cx="15.5" cy="23" rx="2.4" ry="5" fill="#fff" opacity=".28" transform="rotate(18 15.5 23)"/><path d="M24 15.5c-.2-3.4.8-6.4 2.8-8.6" fill="none" stroke="#6D4C2F" stroke-width="2.6" stroke-linecap="round"/><path fill="#00A651" d="M27.4 10.2c2.6-4.4 7.6-5.4 11-4.2-1.4 4-6.4 6.6-11 4.2z"/></svg>
              </div></div>
              <div class="bl-prod bl-prod--box"><div class="bl-prod-y">
                <svg viewBox="0 0 48 48"><path fill="#DDB273" d="M7 15 24 7l17 8-17 8z"/><path fill="#B5844A" d="M7 15l17 8v19L7 34z"/><path fill="#C99A5B" d="M41 15 24 23v19l17-8z"/><path fill="#F4E2BC" d="M13.5 12 30.5 20v6.5l-3.6 1.7V21.8L10 13.6z"/></svg>
              </div></div>
              <div class="bl-prod bl-prod--milk"><div class="bl-prod-y">
                <svg viewBox="0 0 48 48"><rect x="18" y="3" width="12" height="8" rx="2" fill="#00A651"/><path fill="#F7F7F2" d="M19 10h10v5c0 2.2 6 5 6 10.5V43a3 3 0 0 1-3 3H16a3 3 0 0 1-3-3V25.5C13 20 19 17.2 19 15z"/><path fill="#000" opacity=".09" d="M28 15c0 2.2 4 5 4 10.5V43a3 3 0 0 1-3 3h3a3 3 0 0 0 3-3V25.5C35 20 29 17.2 29 15z"/><rect x="13" y="28" width="22" height="9" fill="#FDCD1E"/></svg>
              </div></div>
              <div class="bl-prod bl-prod--greens"><div class="bl-prod-y">
                <svg viewBox="0 0 48 48"><path fill="#8BC34A" d="M20.5 27h7l2 17h-11z"/><circle cx="15" cy="22" r="8" fill="#008A43"/><circle cx="33" cy="22" r="8" fill="#008A43"/><circle cx="24" cy="14" r="9" fill="#00A651"/><circle cx="24" cy="25" r="7.5" fill="#00A651"/><circle cx="20" cy="11" r="2.2" fill="#fff" opacity=".18"/></svg>
              </div></div>
            </div>
            <img class="bl-cart-body" src="/brand/cart-body.webp" width="311" height="241" alt="" decoding="async">
          </div>
          <img class="bl-cart-wheels" src="/brand/cart-wheels.webp" width="311" height="43" alt="" decoding="async">

          <span class="bl-lines bl-lines--enter"><svg viewBox="0 0 30 40"><g stroke="currentColor" stroke-width="3.4" stroke-linecap="round"><path d="M4 6h22"/><path d="M8 20h18"/><path d="M4 34h22"/></g></svg></span>
          <span class="bl-lines bl-lines--l"><svg viewBox="0 0 30 40"><g stroke="currentColor" stroke-width="3.4" stroke-linecap="round"><path d="M6 10 22 4"/><path d="M8 21h16"/><path d="M6 32l16 6"/></g></svg></span>
          <span class="bl-lines bl-lines--r"><svg viewBox="0 0 30 40"><g stroke="currentColor" stroke-width="3.4" stroke-linecap="round"><path d="M6 10 22 4"/><path d="M8 21h16"/><path d="M6 32l16 6"/></g></svg></span>
        </div>
      </div>

      <p class="bl-text">Getting things ready...</p>

      <div class="bl-bar" role="progressbar" aria-label="Loading progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">
        <div class="bl-bar-track"><div class="bl-bar-fill"></div></div>
      </div>
      <span class="bl-sr" aria-live="polite"></span>
    </div>
`;
