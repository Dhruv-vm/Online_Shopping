# BASKET — Version 2.0 Release Notes

**Release Name:** BASKET Version 2.0  
**Release Tag (Proposed):** `v2.0`  
**Base Commit Baseline:** `v1.0` (`68ac8ff`, preserved and unmodified)  
**Branch:** `feature/version-2-development`  
**Date:** November 2026  
**Status:** All Engineering Quality Gates Passed (Functional Freeze)  

---

## 1. Executive Summary

BASKET Version 2.0 represents a major milestone in the evolution of the all-category Indian hyper-local e-commerce marketplace platform. Following the initial Version 1.0 release, Version 2.0 hardens the system against edge-case failures, expands commercial features, adds real-time synchronization, establishes complete database test isolation, and delivers advanced marketplace capabilities across Customer, Retailer, and Admin portals.

All core quality gates have been executed and passed:
- **604 Backend Tests Passed (100%)** with zero failures across 149 seconds of execution.
- **129 Frontend Integration Tests Passed (100%)** with zero failures.
- **39 Database Migrations Verified** (Head: `0039_mission_completion`) with flawless linear upgrade, downgrade, re-upgrade, and full sequential rollback to `0030`.
- **56 Next.js 15 App Router Routes Compiled** into an optimized production build.
- **Strict Lint & Type Safety:** Clean TypeScript compilation (`tsc --noEmit`) and Ruff lint check (`All checks passed!`).

---

## 2. Key Highlights & Features Delivered in Version 2.0

### Phase A: Core Reliability & Idempotency
- **Dukaan vs Dukaan Auction Hardening:** Resolved race conditions during concurrent bid acceptances using PostgreSQL `FOR UPDATE SKIP LOCKED`.
- **Payment Initiation Idempotency:** Implemented client and server idempotency keys with unambiguous conflict resolution on order payments.
- **Transparent Search Resilience:** Engineered PostgreSQL full-text search fallback when OpenSearch indices are unindexed, unbuilt, or unreachable.

### Phase B: Commercial Pricing & Discounts
- **Discount & Coupon Engine:** Backend quote service with coupon validation, stacking limits, category/retailer scoping, minimum order thresholds, and usage tracking.
- **Per-Order Redemption Ledger:** Dedicated database tracking for applied discounts (`discount_redemptions`) preventing duplicate redemptions.
- **Frontend Coupon Input:** Integrated discount code input in the customer shopping basket (`/cart`) with backend-verified pricing and error messaging.

### Phase C: Infrastructure Reliability & Asynchronous Processing
- **Outbox Direct Dispatch Mode (`OUTBOX_DISPATCH=direct`):** Full transactional outbox processing without requiring an external Kafka cluster for local development and edge deployments.
- **Per-Database Search Isolation:** Database-specific OpenSearch index names preventing collision between test, demo, and production environments.
- **Concurrency-Safe Periodic Jobs:** Advisory locks (`pg_try_advisory_xact_lock`) ensuring overlapping scheduled tasks (SLA escalation, stock expiry, reconciliations) never duplicate work or emit duplicate notices.
- **Logging Hygiene:** Structured `job_run` telemetry, `SQL_ECHO` gating, and automatic masking of sensitive credentials, tokens, and passwords.

### Phase D: Multi-Role Portals & Data Isolation
- **Test Database Isolation:** Dynamic creation, migration, and teardown of isolated `*_test` databases per test session, completely protecting `basket_db`.
- **Retailer Push Notifications:** Targeted alerts for RFQs within the retailer's delivery radius, auctions the retailer can supply, auction completions, and paid order notifications (with zero customer PII leakage).

### Final Cycle Marketplace Additions
- **Customer Shopping Intent Workflow (`/account/intent`):** Natural language intent input, whole-word matching against live inventory, automated cart conversion, and automatic demand aggregation into Demand Gap signals for out-of-stock items.
- **Dukaan vs Dukaan Reverse Auctions (`/retailer/auctions`):** Anonymized price ladder, live countdown, atomic closure, and interactive demo simulation for retailers.
- **Real-Time Cross-Portal Sync (SSE):** Shared `EventSource` connection per tab (`lib/realtime.ts`) driving quiet auto-refreshes for products, cart, order tracking, retailer consoles, and notification bell.
- **Community Buying WhatsApp Invitations:** Secure invite tokens and shareable WhatsApp links for group-buy campaigns (`/community-buying/invite/[token]`).
- **Backend-Verified Basket Missions:** Objective progress tracking and backend validation for customer shopping missions (`/missions`).
- **Recurring Baskets (Monthly Essentials):** Scheduled repeat baskets with address and stock pre-validation.
- **Razorpay Sandbox Dual-Mode:** Webhook HMAC verification at `/api/v1/payments/webhook`, Cloudflare tunnel support, server-side capture, and reconciliation.

---

## 3. Test & Verification Metrics

| Suite / Gate | Scope | Status | Notes |
| :--- | :--- | :---: | :--- |
| **Backend Unit & Integration** | 604 tests across all 13 modules | **PASS** | 604 passed, 3 skipped, 0 failed (149.5 s) |
| **Frontend Tests** | 129 integration & unit tests | **PASS** | 129 passed, 0 failed (1.38 s) |
| **TypeScript Type-Check** | `tsc --noEmit` across full frontend | **PASS** | 0 errors |
| **Backend Lint** | `ruff check .` | **PASS** | All checks passed |
| **Frontend Lint** | Next.js ESLint | **PASS** | 0 errors |
| **Next.js Production Build** | Static generation & SSR bundling | **PASS** | 56 routes compiled successfully |
| **Migration Verification** | Up/down/re-up + sequential rollback | **PASS** | All 39 migrations verified (`0039_mission_completion`) |
| **Feature Audit Suite** | 16 business areas | **PASS** | All 16 areas passed (`scripts/audit-features.sh`) |

---

## 4. Migration Summary

- **Baseline:** `0001_initial_baseline`
- **Head:** `0039_mission_completion`
- **Total Migrations:** 39
- **Key New Version 2.0 Migrations:**
  - `0035_discount_codes_redemptions.py`: Discount codes and per-order redemptions.
  - `0036_intent_workflow.py`: Customer shopping intent workflow storage.
  - `0037_group_buy_invites.py`: Community buying peer invitation tokens.
  - `0038_recurring_baskets.py`: Recurring monthly essential baskets.
  - `0039_mission_completion.py`: Basket mission verification records.

---

## 5. Transition to Next Phase

Version 2.0 concludes the core engineering and backend infrastructure enhancement cycle. The codebase is under **UI/UX Freeze** pending the start of the dedicated **Branding, UI, and UX Phase**.
