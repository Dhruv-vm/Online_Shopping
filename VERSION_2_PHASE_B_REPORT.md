# BASKET — Version 2.0 Phase B Report (P0-2 discounts)

> Scope: roadmap **P0-2**, implementation-plan steps **B1–B4**. Phases C and later were **not** started.
> Branch `feature/version-2-development` · Starting commit `8addcd8` · Commits in §13.
> `v1.0` unchanged (`d517b1a`). Nothing pushed, merged, deployed or opened as a PR.

## 1. Approved decisions applied

| Decision | Source |
| --- | --- |
| Stacking: **best single platform discount + the retailer's own offer**; platform deals never stack | Phase B prompt |
| Discount codes: **backend now, checkout input later** (no UI) | Phase B prompt |
| **Store-wide retailer offers apply** to that retailer's items. The minimum is checked on that retailer's lines, and a retailer contributes at most **one** offer per item (the best of its listing and store-wide offers) | Answered 2026-11-21 when the seeded coupons were found to be inapplicable |

## 2. Original defects and root causes

| # | Defect (v1.0 audit) | Root cause |
| --- | --- | --- |
| D2 | Discount codes never checked: coded deals applied to everyone | `get_applicable_discounts_for_listing` never looked at `Discount.code`; the quote request had no code field |
| D3a | All matching deals stacked (two 7 % deals → 14 %) | `calculate_unit_discount` summed every applicable discount |
| D3b | `min_order_paise` compared with the **unit** price | Eligibility was checked per listing with `selling_price_paise < min_order_paise` |
| B4 | `usage_limit` was never reached | `times_used` is read in v1.0 but **never incremented anywhere** (checked with `git grep` on `8addcd8`) |
| — | Store-wide retailer offers (no listing) never applied. All six seeded coupons were inert | The lookup only matched retailer offers through `listing_id` |

## 3. Implementation

**Pricing engine** (`pricing/discount_service.py`, new `resolve_basket_discounts`). Prices the whole basket once.
1. **Code.** A supplied `discount_code` is trimmed and upper-cased, then matched with `upper(code)`. If no live discount has that code (unknown, inactive, not yet valid, expired or used up), the API returns **422 `INVALID_DISCOUNT_CODE`** with one generic message. Nothing about the deal is revealed, and nothing is changed. A blank code counts as no code.
2. **Candidates per line.** Candidates come from the listing, product, category, platform-wide and (new) retailer store-wide scopes. A coded discount is a candidate only when its code was supplied. A listing-bound retailer offer only counts for its own store.
3. **Minimum order.** Each candidate's `min_order_paise` is compared with the **pre-discount subtotal of the basket lines it covers**: item price × quantity, excluding delivery. GST is already inside the item prices and is not added on top. Because discounts never feed into this subtotal, the calculation can't loop.
4. **Selection.** For each line, every pairing of (no retailer offer or one retailer offer) with (no platform deal or one platform deal) is evaluated, and the pairing with the lowest final unit price is kept. Ties go to fewer discounts, then to discount id, so the result is deterministic. The per-discount arithmetic is the unchanged v1.0 `calculate_unit_discount`.

**Quote** (`quote_service.py`, `schemas.py`, `router.py`):
- `POST /quotes` (and `/checkout/quote`) accepts an optional `discount_code` (≤ 50 characters).
- Each quote line stores `applied_discount_ids`. When a price award (negotiation, RFQ, auction, group buy) beats the discounted price, the line's discounts are cleared, so they aren't counted.
- The quote stores `discount_code` only if a coded discount actually priced into it.
- Response additions: `discount_code`, `discount_code_applied`, quote-level `applied_discount_ids`, and per-item `applied_discount_ids`. All are additive.
- Refreshing a quote re-applies its code.
- Orders still copy the quote's totals, so quote, checkout and order stay consistent. The **AI Negotiator** now prices its "list" side with the same engine (no code).

**Usage limits** (new `pricing/redemptions.py`, `orders/service.py`, `payments/reconciliation.py`):
- **At order creation** (same transaction):
  - The discounts on the quote's lines are locked with `SELECT … FOR UPDATE`, in id order.
  - If a discount was deactivated or expired since the quote, the API returns 409 `DISCOUNT_NO_LONGER_AVAILABLE`. If its limit has been reached, it returns 409 `DISCOUNT_USAGE_LIMIT_REACHED`.
  - Otherwise `times_used` goes up by 1 and a `discount_redemptions` row (RESERVED) is written, unique per (discount, order).
  - Any 409 rolls back the whole order: no order row, quote unconsumed, inventory hold still ACTIVE.
- **Release** happens on an unpaid cancel (`cancel_order` from `PENDING_PAYMENT` with no capture) and on payment-window expiry (`execute_75m_sla_escalation_job`). It's one `UPDATE … SET status='RELEASED' WHERE status='RESERVED' RETURNING`, then `times_used = greatest(times_used − 1, 0)` per discount. A second release finds nothing RESERVED and changes nothing. Paid orders are never released.

**Code uniqueness:** admin deal create/update and retailer offer create now reject codes that differ only in case.

## 4. Files changed

| File | Change |
| --- | --- |
| `backend/app/modules/pricing/discount_service.py` | Policy engine, code normalisation, retailer/platform classification. The v1.0 `get_applicable_discounts_for_listing` is kept as a documented candidate lookup and is no longer used for pricing |
| `backend/app/modules/pricing/quote_service.py` | Uses the engine; stores applied ids and the code; refresh keeps the code; response fields |
| `backend/app/modules/pricing/schemas.py`, `router.py` | `discount_code` on the request; new response fields |
| `backend/app/modules/pricing/models.py` | `CheckoutQuote.discount_code`, `CheckoutQuoteItem.applied_discount_ids`, `DiscountRedemption`, index on `superseded_by_quote_id` |
| `backend/app/modules/pricing/redemptions.py` *(new)* | Reserve and release usage |
| `backend/app/modules/orders/service.py` | Reserve on create; release on unpaid cancel |
| `backend/app/modules/payments/reconciliation.py` | Release on payment-window expiry |
| `backend/app/modules/negotiation/service.py` | Same price engine as the quote |
| `backend/app/modules/admin/service.py`, `retailer/service.py` | Case-insensitive code uniqueness |
| `backend/alembic/versions/0035_discount_codes_and_redemptions.py` *(new)* | Migration (§8) |
| `scripts/verify-migrations.sh` | Covers `0035` and the tables it touches |
| `backend/tests/test_migration_lifecycle.py` | New head |
| `backend/tests/test_v2_phase_b_discounts.py` *(new)* | 15 tests |
| `DISCREPANCY_REGISTER.md`, `PHASE_3_FEATURE_TRACKER.md` | Phase B entries |

No frontend files changed.

## 5. API behaviour

```
POST /api/v1/quotes   {"delivery_address_id": "…", "discount_code": "mart10"}   # code optional
201 → { …, "discount_code": "MART10", "discount_code_applied": true,
        "applied_discount_ids": ["…"], "items": [{ …, "applied_discount_ids": ["…"] }] }
422 → {"error": {"code": "INVALID_DISCOUNT_CODE", "message": "This discount code is not valid."}}
POST /api/v1/orders   409 DISCOUNT_USAGE_LIMIT_REACHED | 409 DISCOUNT_NO_LONGER_AVAILABLE
```

A valid code that applies to nothing (wrong category, minimum not met, or a better offer wins) returns 201 with `discount_code_applied: false`.

## 6. Stacking examples (from the automated tests)

| Basket | Eligible | Applied | Unit price |
| --- | --- | --- | --- |
| ₹200 item | Category "20 %, max ₹10"; product flat ₹15 | Flat ₹15 only. The final price decides, not the displayed % | ₹185 |
| ₹1,000 item | Category 5 %; retailer listing 10 %; retailer store-wide 3 % | 10 % + 5 % (one retailer offer + one platform deal) | ₹850 |
| ₹1,000 item | Auto category 5 %; coded category 15 % | No code: 5 %. With code: 15 % only (replaces, doesn't stack) | ₹950 / ₹850 |
| 2 × ₹200 | Category 10 %, minimum ₹400 | Applies at exactly ₹400. The discounted ₹360 doesn't undo it, and ₹360 + ₹49 delivery doesn't qualify a ₹400.01 minimum | ₹180 |

## 7. Seeded demo discounts: expected vs actual

Fresh isolated `basket_v2b_demo` built with `scripts/reset-demo-db.sh` at head `0035`, and the API from this working tree. Expected values were computed independently by the probe (`backups/mc/v2b_seeded_probe.py`; results in `backups/mc/v2b_seeded_results.json`). No discount records were invented. **20 / 20 checks PASS.** None of the 8 seeded discounts has a usage limit.

| Seeded discount | Case | Basket | Code | Expected | Actual | |
| --- | --- | --- | --- | --- | --- | :---: |
| MART10 (Basket Mart, 10 %, min ₹500, max ₹150) | below minimum | 1 × ₹360 | mart10 | ₹0 off | ₹0 off, payable ₹409 (₹49 delivery), code_applied false | PASS |
| | no code | 2 × ₹360 | — | ₹0 off | ₹0 off, ₹720 | PASS |
| | with code | 2 × ₹360 | mart10 | ₹72 off, ₹648 | ₹72 off, ₹648 | PASS |
| LIFE15 (Basket Lifestyle, 15 %, min ₹1,000, max ₹300) | below minimum | 1 × ₹320 | life15 | ₹0 off | ₹0 off, payable ₹369 | PASS |
| | no code | 4 × ₹320 | — | ₹0 off | ₹0 off, ₹1,280 | PASS |
| | with code | 4 × ₹320 | life15 | ₹192 off, ₹1,088 | ₹192 off, ₹1,088 | PASS |
| NAMMAD10 (Namma Digital, 10 %, min ₹999, max ₹500) | below minimum | 1 × ₹623.99 | nammad10 | ₹0 off | ₹0 off | PASS |
| | no code | 2 × ₹623.99 | — | ₹0 off | ₹0 off, ₹1,247.98 | PASS |
| | with code | 2 × ₹623.99 | nammad10 | ₹124.80 off, ₹1,123.18 | ₹124.80 off, ₹1,123.18 | PASS |
| NAMMADFEST (₹150 off, ended 16 Nov) | expired | 1 × ₹623.99 | nammadfest | 422 | 422 `INVALID_DISCOUNT_CODE` | PASS |
| Flash deal 12 % (Namma Digital, one listing, no code) | automatic | 1 × ₹1,01,594.99 | — | ₹12,191.40 off, ₹89,403.59 | same | PASS |
| | with store code | 1 × ₹1,01,594.99 | NAMMAD10 | 12 % only (NAMMAD10 is capped at ₹500) | ₹12,191.40 off, code_applied false | PASS |
| GHARGH10 (Ghar Ghar, 10 %, min ₹999, max ₹500) | below minimum | 1 × ₹383.99 | ghargh10 | ₹0 off | ₹0 off, payable ₹432.99 | PASS |
| | no code | 3 × ₹383.99 | — | ₹0 off | ₹0 off, ₹1,151.97 | PASS |
| | with code | 3 × ₹383.99 | ghargh10 | ₹115.20 off, ₹1,036.77 | ₹115.20 off, ₹1,036.77 | PASS |
| GHARGHFEST (₹150 off, ended 16 Nov) | expired | 1 × ₹383.99 | gharghfest | 422 | 422 `INVALID_DISCOUNT_CODE` | PASS |
| Flash deal 12 % (Ghar Ghar) | automatic | 1 × ₹7,183.99 | — | ₹862.08 off, ₹6,321.91 | same | PASS |
| | with store code | 1 × ₹7,183.99 | GHARGH10 | 12 % only | ₹862.08 off, code_applied false | PASS |
| MART10 usage | order, then unpaid cancel twice | 2 × ₹360 | mart10 | `times_used` 0 → 1 → 0; RESERVED → RELEASED; order total = quote total | 0 → 1 → 0; RESERVED → RELEASED; ₹648 = ₹648 | PASS |

v1.0 comparison:
- The two flash deals were the only seeded discounts that applied in v1.0, and they still apply automatically at the same 12 %.
- The six store-wide coupons never applied before. They now work with their code, subject to the minimum.

## 8. Migration `0035_discount_codes_redemptions`

| Change | Kind |
| --- | --- |
| `checkout_quotes.discount_code` VARCHAR(50) NULL | add column |
| `checkout_quote_items.applied_discount_ids` JSONB NOT NULL DEFAULT `'[]'` | add column (existing rows get `[]`) |
| `discount_redemptions` (FKs to `discounts` and `orders`, ON DELETE CASCADE; unique (discount_id, order_id); status check) + `ix_discount_redemptions_order_id` | new table |
| `ix_checkout_quotes_superseded_by_quote_id` | index on a **pre-existing** unindexed FK, flagged by the verify script once `checkout_quotes` was in scope |

- No index was added on `discounts(code)`: it already has a unique index, and the table holds at most hundreds of rows.
- `scripts/verify-migrations.sh` on a throwaway `basket_migration_verify` database: up, down (exact schema restore), re-up, sequential rollback to `0030` and re-apply all **PASS**. No NOT VALID constraints. Every FK on the touched tables is indexed.
- `alembic check` shows no drift from `0035`; only the pre-existing MC-09 items remain.
- Applied to `basket_db_test` (by the test suite) and `basket_v2b_demo`. **Not** applied to `basket_db`.

## 9. Tests and results

| Check | Result |
| --- | --- |
| `test_v2_phase_b_discounts.py` | **15 passed** |
| Backend full suite | **569 passed, 0 failed, 3 skipped** (Phase A: 554; +15). Includes all Phase A tests and every existing discount, quote, order, payment and negotiator test |
| E2E journeys + role suites | 14 / 14 |
| `scripts/audit-features.sh` (16 areas) | all passed |
| `scripts/verify-migrations.sh` | ALL MIGRATION CHECKS PASSED |
| `ruff check` / `ruff format --check` | clean / 281 files |
| Frontend (untouched) test / type-check / lint / build | 129/129 · 0 errors · 0 errors (1 pre-existing warning) · 63 routes |
| Live seeded probe | 20 / 20 PASS, no errors in the API log |

The 15 tests cover:
- **Codes:** a coded deal isn't applied without its code; lower/upper/mixed case with spaces all match; wrong, expired, inactive, not-yet-valid and used-up codes return 422; a blank code is ignored; a valid code can't bypass category or minimum.
- **Stacking:** only the best platform deal applies, chosen by final price; platform deal + retailer offer apply together; only one retailer offer per item; a coded deal replaces the automatic one rather than stacking.
- **Minimum order:** checked on the basket subtotal, with multiple quantities and multiple products, excluding tax and delivery, with no circularity; a store-wide offer's minimum uses that store's lines only.
- **Usage:** a use is reserved at order creation and released once on an unpaid cancel (repeat cancel and a manual duplicate release change nothing); payment-window expiry releases once, even if the job runs twice and the customer cancels afterwards; a paid, then cancelled order keeps its use.
- **Concurrency:** concurrent orders at limit 1 with 2 buyers and limit 2 with 5 buyers.
- **Rollback and history:** a deal deactivated after the quote blocks the order with 409; existing orders keep their stored totals; code uniqueness is case-insensitive.

Automated vs live:
- Everything above, except the seeded probe, is automated against `basket_db_test`.
- The seeded probe is live API + DB verification on an isolated demo database.
- No payment provider was involved.

## 10. Concurrency verification

This uses real PostgreSQL transactions, not mocks. In `test_concurrent_orders_never_exceed_usage_limit`:
1. Every buyer gets a quote priced with the deal (all saw `times_used = 0`) and a reservation.
2. All order requests are fired at once with `asyncio.gather`, each in its own database session.

Results:
- Exactly `limit` orders succeed (1 of 2; 2 of 5). The rest get 409 `DISCOUNT_USAGE_LIMIT_REACHED`.
- `times_used` equals the limit, with exactly `limit` redemption rows.
- Every loser has no order row, an ACTIVE unconsumed quote and an ACTIVE inventory hold, so the rollback is complete.

Double release (cancel + expiry) is covered by the RESERVED → RELEASED compare-and-set and tested in both orders.

## 11. Impact

- **UI/UX:** none. No frontend file changed. The checkout page doesn't send a code and shows no coupon field. Customers **cannot** redeem codes through the UI yet; that's by design. The quote response only gains fields, so the checkout page renders as before.
- **Database:** additive migration only. `basket_db` was not touched. Historical orders and quotes are never recalculated. Existing quote lines get `applied_discount_ids = []`.
- **Security:**
  - Codes are validated server-side, and errors are generic.
  - Customer, retailer and admin boundaries are unchanged; the quote still uses the caller's own basket and address.
  - Usage is enforced under row locks.
  - No secrets in code, tests, logs or docs.

## 12. Remaining limitations

- **No checkout code input** (deferred until UI approval).
- **Fixed-amount offers are per unit** (v1.0 arithmetic, unchanged). For example, "₹150 off" takes ₹150 off each unit, and `max_discount_paise` caps per unit. A per-order fixed discount would need a product decision.
- **Partial-capture rejection** cancels an order without releasing its discount use (conservative). Only unpaid cancellation and payment-window expiry release.
- **Order-time recheck** covers deactivation, expiry and the usage limit. Other deal edits between quote and order (value, scope) are not re-priced; the order keeps the quote's price, as in v1.0.
- **Codes are not rate-limited** (abuse limits are P2-2).
- Uncoded store-wide retailer offers that already exist in `basket_db` will now apply to **new** quotes (approved behaviour). Existing orders are unchanged.

## 13. Git

| Commit | Content |
| --- | --- |
| `438fbd3` | feat(pricing): discount codes, single-platform-deal stacking and basket-subtotal minimum (B1–B3) + migration 0035 |
| `72f4073` | feat(pricing): concurrency-safe discount usage limits (B4) |
| (this commit) | test+docs: Phase B tests, discrepancy register, feature tracker, this report |

Local commits only, authored by Dhruv-vm. **Phase B stops here. Phase C is not started.**
