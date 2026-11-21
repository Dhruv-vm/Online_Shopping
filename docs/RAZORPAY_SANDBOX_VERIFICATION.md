# Razorpay Sandbox Verification (Version 2.0 Phase C1)

> **Test mode only.** Keys in `.env` start with `rzp_test_`; the verification script refuses anything else. No real money moved. No secret appears in this document.
> Environment: isolated database `basket_c1_demo` (built with `scripts/reset-demo-db.sh`), API from branch `feature/version-2-development` on port 8001, `OUTBOX_DISPATCH=direct`, frontend dev server from a temporary copy on port 3001.
> Date: 2026-11-21. Harness: `backups/mc/c1_sandbox.py` (gitignored, repo-local) + Playwright.

## Results

| # | Scenario | Status | Provider ids | Expected | Actual |
| --- | --- | :---: | --- | --- | --- |
| 1 | Successful hosted checkout | **PASS** (see note) | order `order_U2p9vWMR6qR89x`, payment `pay_U2pCOR8PdXQxZg` | Payment captured; attempt SUCCEEDED; order CONFIRMED | Razorpay API: order `paid`, payment `captured`, method `netbanking`, ₹369.00 = order total. BASKET: attempt `SUCCEEDED`, capture `CAPTURED`, order `CONFIRMED`, payment status `SUCCEEDED` (order `BSK-20261121-D415B9E9`) |
| 2 | Payment failure + retry | **NOT EXECUTED** | — | Attempt FAILED, retry possible, no wrong capture | Needs the hosted checkout's failure path **and** the `payment.failed` webhook (or reconciliation) to observe FAILED; scheduled with scenario 4 |
| 3 | Checkout closed, then expiry | **PASS** | order `order_U2pZUMYyQPN6Od` | Order stays payable while the window is open; expiry cancels it and releases stock | Window closed unpaid → Razorpay order stayed `created`; paying again returned the **same** Razorpay order; reservation held (`ALLOCATED_TO_ORDER`). After the window expired the SLA job cancelled the order (`CANCELLED`, payment `FAILED`, attempt `FAILED`) and released the reservation; stock back to 50 on hand / 0 reserved (order `BSK-20261121-FCDFCBB3`) |
| 4 | Webhook-only confirmation | **BLOCKED** | — | Webhook alone confirms the payment | Needs `RAZORPAY_WEBHOOK_SECRET` in `.env` and a webhook registered in the Razorpay Test Dashboard pointing at a public tunnel (see Runbook) |
| 5 | Admin refund | **PASS** | refund `rfnd_U2pZ1tl7BLddPb` on `pay_U2pCOR8PdXQxZg` | Refund created at Razorpay; refund, capture, order and analytics updated | `POST /orders/{id}/refunds` (admin) → 201; Razorpay API: refund `processed`, ₹369.00. Same idempotency key → same refund; customer self-refund → 403. Without webhooks, the refund-reconciliation job (refunds > 2 min old) set refund `REFUND_PROCESSED`, capture `REFUNDED`, order payment status `REFUNDED`; admin overview `refunded_paise` 0 → 36900 |
| 6 | Ambiguous creation → reconciliation | **PASS** | order `order_U2pZdtnNgeXQEo` | CREATION_AMBIGUOUS attempt recovered to the real Razorpay order | Real order created, then the attempt was put in `CREATION_AMBIGUOUS` with no provider id (simulating a lost gateway response). New initiation → 409 `PAYMENT_ATTEMPT_AMBIGUOUS`. Reconciliation (receipt search) recovered the attempt: status `PENDING`, provider id = the real order, order payment status `PENDING` (order `BSK-20261121-3FFA4A04`) |

**Note on scenario 1.** The checkout was driven through the real BASKET UI (login → basket → reserve → confirm order → **Pay** → Razorpay hosted checkout, test mode). The automation's connection to the computer dropped after entering the test phone number; the remaining payment-method step was completed in the visible browser window **outside the automation** (presumably by the user — please confirm). Everything after it — signature verification, server-side capture and order confirmation by BASKET — ran in the application and was verified above against Razorpay's API.

**Note on scenario 6.** The first reconciliation, run ~1 s after the Razorpay order was created, found no match: Razorpay's receipt search had not indexed the order yet. The production job only looks at attempts older than 5 minutes, so this lag is covered; a second run resolved it.

**Note on scenario 5.** Refunds are confirmed by the `refund.processed` webhook or, as here, by reconciliation after 2 minutes. The admin overview's `total_revenue_paise` is unchanged by the refund (refunds are reported separately in `refunded_paise`) — existing v1.0 analytics behaviour, recorded rather than changed.

No defects were found in the payment code during C1.

## Runbook (to complete scenarios 2 and 4)

1. Choose a random string and add `RAZORPAY_WEBHOOK_SECRET=<it>` to the repo-root `.env` (never commit it).
2. Start the API on an isolated demo database (example):
   `cd backend && DATABASE_URL=<…/basket_c1_demo> OUTBOX_DISPATCH=direct .venv/bin/uvicorn app.main:app --port 8001`
3. `cloudflared tunnel --url http://localhost:8001` → note the `https://<name>.trycloudflare.com` URL.
4. Razorpay Dashboard → **Test Mode** → Settings → Webhooks → Add: URL `https://<name>.trycloudflare.com/api/v1/payments/webhook`, same secret, events `payment.authorized`, `payment.captured`, `payment.failed`, `refund.processed`, `refund.failed`.
5. Scenario 2: pay with Netbanking → any bank → **Failure** on Razorpay's test bank page; confirm the attempt becomes `FAILED` (webhook) and that paying again succeeds without a second capture.
6. Scenario 4: start a payment, complete it on the bank page, and close the browser before the BASKET page receives the result; confirm the webhook alone confirms the order (`CONFIRMED`, capture recorded once).
7. Record provider ids here. Remove the webhook from the Dashboard afterwards if it is no longer needed.
