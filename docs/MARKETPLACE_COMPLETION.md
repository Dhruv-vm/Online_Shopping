# BASKET — Marketplace Completion: Release Audit Report

> Branch `feature/marketplace-completion` · local only — **not pushed, no PR, not merged, not deployed**
> Base `integration` @ `2610a1e` · Final HEAD: see `git log -1` (recorded in the handoff message)
> Author `Dhruv-vm <vmdhruv1@gmail.com>`, no co-author or session trailers · 2026-11-21
> Everything below was executed on the developer Mac against isolated databases. Nothing is extrapolated.

Related: [`EXTERNAL_CONFIGURATION.md`](EXTERNAL_CONFIGURATION.md) · `DISCREPANCY_REGISTER.md` §MC · `TEST_REPORT.md` · screenshots in [`screenshots/marketplace-completion/`](screenshots/marketplace-completion/) (feature pages) and [`screenshots/marketplace-completion/audit/`](screenshots/marketplace-completion/audit/) (release-audit actions).

---

## 1. Summary

The branch fixes the defects in the original assignment and builds the following:
- **Original defects fixed:** polluted data, 0 % offers, fabricated analytics, the empty admin card and the language selector.
- **Built:** the storefront, the customer/retailer/admin portals, the 12-language infrastructure and the remaining Phase 3 functionality.

The release audit added a migration-verification and a feature-audit tool, and found and fixed seven more defects. Most features are complete end to end. **Multilingual coverage is partial**, and **Razorpay, OCR, AI and object storage need external configuration or further code** (§7–8).

## 2. Defects found and fixed during the release audit

| # | Found by | Defect | Commit |
| --- | --- | --- | --- |
| 1 | Migration integrity check | 8 foreign-key columns had no usable index (5 from `0031`, 3 older) | `ed02080` (`0034`) |
| 2 | Flaky-test investigation | `test_budget_shortfall_handling` depended on leftover rows in the shared test DB (planner searched the whole catalogue) | `f280d8e` |
| 3 | Feature audit | `test_mission_recommendation_personalized_by_intent` — same cause (planner widened to all categories, kept the 100 cheapest; 154 cheaper fixtures existed) | `ccc466d` |
| 4 | Browser audit | List to Basket offered search hits the database could not sell; build-cart then refused them | `ea556d4` |
| 5 | Browser audit | Admin suspension / RFQ-moderation reasons were required but discarded | `6b8bc5a` |
| 6 | Browser audit | Retailer RFQ bid could be submitted with nothing offered (raw 422) | `8de5111` |
| 7 | Final regression | E2E journey test file not `ruff format`-clean | `2931e74` |

Root cause of #2/#3, classified as requested: **shared database state + test ordering + no fixture cleanup**. Not background jobs and not time-dependent logic. Both were reproduced deterministically before fixing, and no assertion was weakened; #2 gained stronger assertions.

Environment finding (not a code defect, documented as MC-12): the repo-root `.env` points OpenSearch at a shared index built from `basket_db`. An API started against another database searches the wrong products. Demo/E2E APIs must be started with `OPENSEARCH_URL=""`.

## 3. Migration verification (`scripts/verify-migrations.sh`)

Run on a freshly created throwaway database `basket_migration_verify` (dropped afterwards). The script refuses any name not ending `_verify`, so `basket_db` and production cannot be touched.

| Check | 0031 | 0032 | 0033 | 0034 |
| --- | :---: | :---: | :---: | :---: |
| Upgrade from previous revision | ✅ | ✅ | ✅ | ✅ |
| Downgrade restores previous schema exactly (pg_dump diff) | ✅ | ✅ | ✅ | ✅ |
| Re-upgrade reproduces identical schema | ✅ | ✅ | ✅ | ✅ |

- Sequential rollback `0034 → 0030` matches the original schema ✅; re-apply to head matches the first upgrade ✅.
- No `NOT VALID` constraints ✅.
- Every FK on the touched tables has a full leading index ✅ (after `0034`).
- Foreign keys and delete rules verified, e.g. `price_alerts.user_id → users ON DELETE CASCADE`, `price_alerts.triggered_listing_id → product_listings SET NULL`, `group_buy_campaigns.template_id → group_buy_templates SET NULL`, `admin_audit_logs.actor_user_id → users SET NULL`.
- `alembic check`: no drift involving `0031`–`0034` tables. Pre-existing drift elsewhere is unchanged (MC-09).
- Databases: `basket_demo` at `0034`; **`basket_db` deliberately left at `0033`** — run `alembic upgrade head` (indexes only).

## 4. Feature-by-feature completion matrix

API = automated tests (`scripts/audit-features.sh`, final run). Browser = Playwright against `basket_demo`, release audit.

| Feature | API tests | Browser verification | Status |
| --- | --- | --- | --- |
| Common authentication & role redirects | 34 ✅ | customer → `/`, retailer → `/retailer`, admin → `/admin`; wrong password message; expired-session notice; customers see "Administrators only" / "This area is for retailers" | ✅ Complete |
| Customer-only checkout | 23 ✅ | Retailer sees "Checkout is for shopper accounts"; server returns 403 to business sessions | ✅ Complete |
| Retailer onboarding & approval | 6 ✅ | Register → onboarding, portal restricted → admin approves from desk → full portal | ✅ Complete |
| Product creation & image uploads | 20 ✅ | Retailer published a listing (201); listing photo upload ("Photo updated…"); admin canonical image upload (API test) | ✅ Complete (local disk storage — MC-06) |
| Inventory updates | 26 ✅ | Stock adjusted to 20 with reason | ✅ Complete |
| Retailer order fulfilment (payment-gated) | 87 ✅ | Paid order processed → packed → shipped → delivered; unpaid orders refused (API) | ✅ Complete |
| Admin governance & audit | 4 ✅ (+ journey C) | Approve store; suspend + reinstate with reason; both actions in audit log with reason | ✅ Complete |
| Community buying (3B) | 7 ✅ | Start a group on retailer terms; "already have an open group" message | ✅ Complete |
| RFQs (3C) | 3 ✅ | Customer posted request; retailer bid ₹1,444.99 | ✅ Complete |
| Dukaan vs Dukaan (3E) | 2 ✅ | Customer started 90-s auction; retailer bid ₹99,000; customer saw "#1 … save ₹1,807.99" live | ✅ Complete |
| AI Negotiator (3D) & deal assistant | 7 ✅ | Counter-offer moved store offer ₹94,202.65 → ₹92,756.37; assistant answered from live catalogue | ✅ Rule-based (no LLM — MC-07) |
| Price Intelligence & Sale Stream (3F/3G) | 7 ✅ | Product page: 90-day history with demo-data notice, other-store prices, price alert; Sale Stream add to basket | ✅ Complete |
| Demand Gap (3A) | 7 ✅ | Admin demand page KPIs and empty states | ✅ Complete |
| OCR / manual fallback (3I) | 6 ✅ (+ stale-hit test) | "Manual entry" labelled; text list matched and "2 item(s) added" | ✅ Manual / ⚠ OCR needs provider (MC-08) |
| Multilingual (3H) | 19 ✅ | 12 languages, Urdu RTL, persistence verified; **in Hindi, cart, checkout, orders, account, admin catalogue/retailers and most retailer pages stay English** | ⚠ **Partial** — ≈32 % of page strings translated (MC-01) |
| Phase 2 (missions, substitutes, intent, passport) | 42 ✅ | — | ✅ (unchanged) |

## 5. Test results (final regression)

See `TEST_REPORT.md` for the full table and commands.

## 6. Screenshots

- `docs/screenshots/marketplace-completion/` — 33 page screenshots: customer (01–10, 29–30), retailer (11–17), admin (18–26), languages hi/kn/ur (26–28).
- `docs/screenshots/marketplace-completion/audit/` — 19 release-audit screenshots of performed actions: Sale Stream, assistant, list-to-basket, product price intelligence, group buying, auctions (customer and retailer bid), negotiator, RFQ bid, add product, listing photo, offer, fulfilment, onboarding, admin approval, audit log, Hindi catalogue and retailer listings.

## 7. External configuration needed

Exact steps in [`EXTERNAL_CONFIGURATION.md`](EXTERNAL_CONFIGURATION.md):
- Razorpay test keys and webhook (backend only).
- OCR adapter contract.
- No AI-provider integration exists (code required).
- Local media storage only (S3 not implemented).
- Kafka / OpenSearch.
- The per-database search-index rule.
- `basket_db` upgrade to `0034`.

## 8. Known limitations

From `DISCREPANCY_REGISTER.md` §MC:
- **MC-01:** multilingual partial.
- **MC-02:** Razorpay hosted payment not exercised in the browser.
- **MC-03:** `basket_db` at `0033`.
- **MC-04:** shared persistent test DB.
- **MC-05:** no public store page.
- **MC-06:** local media only.
- **MC-07:** rule-based assistant.
- **MC-08:** OCR adapter unverified live.
- **MC-09:** pre-existing Alembic drift.
- **MC-10:** demo data now includes release-audit records.
- **MC-11:** unused `NEXT_PUBLIC_RAZORPAY_KEY_ID`.
- **MC-12:** shared search index.

## 9. Run commands

```bash
# Backend (demo DB; search via PostgreSQL)
cd backend
DATABASE_URL="$(grep -E '^DATABASE_URL=' .env | cut -d= -f2- | sed -E 's#/basket_db(\?|$)#/basket_demo\1#')" \
  OPENSEARCH_URL="" .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000

# Frontend
cd frontend && npm run build && npx next start -p 3000

# Verification
cd backend && unset DATABASE_URL && .venv/bin/python -m pytest -q -p no:cacheprovider
scripts/audit-features.sh
scripts/verify-migrations.sh
cd frontend && npm test && npm run type-check && npm run lint && npm run build

# Data
scripts/reset-demo-db.sh                                   # basket_demo only
cd backend && .venv/bin/alembic upgrade head               # basket_db → 0034
```

Demo accounts (`basket_demo`, password `Basket@123`):
- `customer@basket.demo`
- `retailer1@basket.demo` … `retailer4@basket.demo`
- `admin@basket.demo`
