# Recurring Basket — "Basket Monthly Essentials" — Implementation Report

**Status:** scheduling and the safe preparation workflow are implemented and tested.
**Automatic payment is NOT implemented.** Every response reports `autopay: "NOT_ENABLED"`.

## What the customer can do (`/account/recurring`, nav "Monthly Essentials")

| Action | How |
|---|---|
| Select existing basket | "Create from my current cart" snapshots the cart's items, quantities and set-up prices |
| Monthly schedule / day of month | Day 1–28. Days 29–31 are excluded so every month has the date. |
| Start date / optional end date | Validated; past the end date the basket becomes `ENDED` |
| Delivery address | Optional; one of the customer's own addresses (another user's address gives 404) |
| Review recurring items | Listed with store and set-up price |
| Edit schedule / quantities | `PATCH`: day, start, end (or clear it), address, quantities (0 removes; at least one item must remain) |
| Pause / resume | `next_run_date` is cleared while paused and recomputed on resume |
| Skip one month | Skips only the next date (recorded as a `SKIPPED` run) |
| Cancel | Final; a cancelled basket cannot be resumed (409) |

## Before each scheduled order: the pre-order check

`GET /recurring-baskets/{id}/check` runs any time. The hourly background job also runs
it automatically **one day before** each date. It reports, from live data:

- **Current price** against the set-up price (`PRICE_CHANGED`).
- **Inventory:** `OUT_OF_STOCK`, or `LOW_STOCK` with the quantity that can be supplied.
- **Offers:** the real discount engine (`resolve_basket_discounts`) gives the final unit price and the offer names.
- **Delivery:** whether the store serves the address PIN (`NOT_DELIVERABLE`).
- **Availability:** listing or store inactive (`UNAVAILABLE`).
- **Updated total:** items after offers, orderable lines only, next to the same lines at set-up prices.
  Delivery fee and GST are calculated at checkout, and the check says so.

The job creates one `recurring_basket_runs` row per (basket, date). This is a unique
constraint, so a date is prepared and notified **once** however often the job runs.
The customer gets one in-app notification ("… is ready to review — items ₹X, N changes.
Nothing is charged until you check out.").

**Load into cart** puts the orderable lines into the cart. The customer then checks out
through the normal quote → reservation → payment flow. **No order is created and no
payment is attempted by this feature**; tests assert the order and payment tables are
unchanged.

## Autopay — why it is not enabled, and what it needs
The brief's preconditions, none of which can be met safely without provider and owner approval:

1. **Explicit consent**, recorded per basket, with the amount or amount cap shown.
2. **A supported provider mandate**, e.g. a Razorpay recurring/subscription or e-mandate
   (UPI AutoPay / card mandate under RBI e-mandate rules: pre-debit notification at
   least 24 h ahead, AFA above the limit). This needs the merchant account to be enabled
   for recurring payments and the owner's approval.
3. **Pre-charge notification**: the existing day-before notice is the natural hook.
4. **Pause and cancel** (implemented) must also cancel the mandate.
5. **Failure handling and a retry policy** (for example one retry after 24 h, then pause and notify).
6. **Stock or price changes**: charge only the re-checked total, and only if it is within the consented cap; otherwise ask.
7. **No card storage**: tokens stay with the provider. Basket stores none. This module has no payment fields.

## Data
Migration `0038_recurring_baskets` (with downgrade):
- `recurring_baskets`: customer, name, items JSON snapshot, `day_of_month` (check
  constraint 1–28), `start_date`, `end_date`, `delivery_address_id`, `status`,
  `skip_dates`, `next_run_date`.
- `recurring_basket_runs`: `scheduled_for`, status `PREPARED`, `LOADED_TO_CART` or
  `SKIPPED`, the check JSON, and a unique constraint on (basket, date).

## Tests (`backend/tests/test_final_recurring_basket.py`)
- Date rules: next occurrence, skip, end date.
- Schedule, edit, skip, pause, resume, cancel; another customer gets 404.
- After a price rise, the check shows `PRICE_CHANGED` 200 → 220 and the updated total.
- Preparation runs once per date with a single notification.
- Load into cart adds items and creates no order and no payment.
