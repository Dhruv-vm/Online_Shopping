# BASKET Version 1.0 — Round 1 Submission
## Official Release Notes & Milestone Report

---

### Release Identity

| Field | Detail |
|---|---|
| **Project** | BASKET |
| **Version** | 1.0 |
| **Release Name** | BASKET Version 1.0 — Round 1 Submission |
| **Purpose** | Round 1 Project Presentation / Evaluation |
| **Working Branch** | `feature/marketplace-completion` |
| **Git Tag** | `v1.0` |
| **Release Date** | November 21, 2026 |
| **Target Milestone** | Presentation & Technical Evaluation Milestone |

---

## 1. Executive Summary

BASKET is an enterprise-grade multi-category, multi-retailer e-commerce marketplace engineered for local commerce across India. Designed to empower local kirana stores, regional merchants, and national retail brands, BASKET bridges hyperlocal accessibility with modern quick-commerce agility across **Groceries & Food**, **Fashion & Apparel**, **Consumer Electronics**, and **Beauty & Lifestyle**.

Version 1.0 represents the culmination of Phase 1 (Core Multi-Retailer Marketplace), Phase 2 (Customer Intelligence: Mission Planner, Substitute Intelligence, Intent Memory, and Product Passport), Phase 3 (Advanced Marketplace Capabilities: Demand Gap, Community Buying, RFQ Exchange, AI Negotiator, Dukaan vs Dukaan Bidding, Price Intelligence, Sale Stream, Bharat Multilingual, and List-to-Basket OCR), and the Marketplace Completion hardening sprint.

---

## 2. Platform Roles & Core Capabilities

### 2.1 Customer Experience
- **Quick-Commerce Storefront:** High-performance, mobile-responsive UI inspired by modern Indian quick-commerce interfaces, featuring category navigation, instant search, dynamic filtering, and localized promotional banners.
- **Multi-Category Breadth:** Seamless browsing and purchasing across groceries, daily staples, clothing, electronics, and personal care.
- **Cart & Customer-Only Checkout:** Secure cart management with server-side HMAC quote signing, pincode serviceability validation, and strict role enforcement ensuring only customer accounts can check out.
- **Customer Intelligence (Phase 2):**
  - **Intent Memory:** Remembers shopping routines, replenishment cycles, and past preferences.
  - **Substitute Intelligence:** Recommends equivalent alternatives when items are out-of-stock.
  - **Mission Planner:** Goal-oriented basket generation (e.g. weekly groceries, party supplies, festive shopping).
  - **Product Passport:** Complete ingredient transparency, country of origin, manufacturing details, and allergen warnings.
- **Wishlist & Saved Addresses:** Multi-address management with geocoded pincode matching and quick default selection.

### 2.2 Retailer Portal
- **Merchant Onboarding & Verification:** Self-service registration with document upload for KYC verification.
- **Catalogue & Listing Management:** Full lifecycle control over product listings, SKU variants, pricing, stock levels, and category mappings.
- **Order Fulfillment Workflow:** Multi-stage order processing pipeline: `PAID` $\rightarrow$ `CONFIRMED` $\rightarrow$ `PACKED` $\rightarrow$ `SHIPPED` $\rightarrow$ `DELIVERED`, with strict state-transition guards preventing unfulfilled or unpaid bypasses.
- **Dynamic Bidding & Group Deals:** Retailer controls to publish Community Buying deal tiers and participate in Dukaan vs Dukaan reverse auctions.
- **Price Insights & Alerts:** Automated competitor price tracking and margin protection alerts.

### 2.3 Administrator Governance Console
- **KYC & Merchant Moderation:** Review, approve, or reject retailer verification documents with audit logging.
- **Catalogue Governance:** Global category tree management, product approval controls, and brand governance.
- **Discounts, Offers & Deals:** Centralized creation and moderation of platform-wide promotional discounts, category deals, and basis-point fee structures.
- **Marketplace Health & Audit Logs:** Real-time visibility into outbox event streaming, transaction logs, and platform metrics.
- **Community Moderation:** Moderation over Community Exchange RFQs and live reverse auctions.

---

## 3. Phase 3 Advanced Capabilities Breakdown

BASKET Version 1.0 incorporates the complete suite of 9 Phase 3 capabilities:

### 3A. Demand Gap & Unmet Demand Aggregation
- Automatically tracks zero-result searches, out-of-stock product views, and unmet customer demand requests.
- Aggregates localized demand into category and pincode pools, providing retailers and platform admins actionable insights into inventory gaps.

### 3B. Basket Community Buying (Group Purchasing)
- Social commerce group buying mechanism where customers pool orders to unlock volume-tiered wholesale discounts.
- Retailer-published discount templates, member progress tracking with initials-based privacy, stock-safe inventory allocation, and automatic group-price settlement upon threshold completion.

### 3C. Basket Community Exchange (Customer RFQs)
- Reverse-marketplace where customers post customized requests for quotation (RFQs) for bulk or specialty purchases.
- Verified retailers submit competitive price and fulfillment bids; customers review and accept quotes directly into checkout.
- Full administrator moderation and cancellation controls.

### 3D. AI Negotiator / Deal Assistant
- Conversational cart-level discount negotiation engine (`POST /api/v1/assistant/chat`).
- Operates in a deterministic, transparent `mode=rule_based` evaluating live cart items against retailer-configured discount ladders and floor price margins.

### 3E. Dukaan vs Dukaan (Multi-Retailer Live Bidding)
- 90-second rapid reverse auction allowing local retailers to compete on price and delivery time for customer shopping baskets.
- Real-time bid evaluation, countdown timers, tie-breaking algorithms, and administrative oversight consoles.

### 3F. Basket Price Intelligence & Historical Price Trends
- Transparent 90-day price history tracking and discount verification to protect consumers from artificial markups.
- Cross-store price comparisons, automated drop alerts, and retailer margin analytics with distinct labeling for demo seed histories.

### 3G. Sale Stream (Real-Time Flash Deals Feed)
- Live flash deal feed delivering limited-time, limited-quantity promotional events to the customer homepage.
- Efficient cursor-based polling (`since` cursor).
- **Explicit Scope Boundary:** "Sale Stream Rewind" was permanently cancelled and removed from requirements; expired events are never served.

### 3H. Bharat Multilingual (Regional Indian Languages)
- Multi-language localization architecture supporting 12 Indian languages: English, Hindi, Bengali, Telugu, Marathi, Tamil, Urdu (with RTL layout support), Gujarati, Kannada, Odia, Malayalam, and Punjabi.
- Persistence across HTTP cookies, browser `localStorage`, and authenticated user profiles.

### 3I. Handwritten List to Basket (Vision OCR)
- Smart cart onboarding enabling customers to submit unstructured shopping lists (text or image) to parse and match against catalogue listings.
- Provider-reported confidence scores per line item, "please check" flags for ambiguous items, and manual fallback editing when OCR engines are inactive.

---

## 4. Technical Architecture & Engineering Standards

- **Backend Architecture:** Built on FastAPI (Python 3.12) adopting Domain-Driven Design (DDD) across modular business domains (`auth`, `catalogue`, `orders`, `payments`, `retailers`, `search`, `intelligence`, etc.).
- **Database & Migrations:** PostgreSQL 16+ using SQLAlchemy 2.0 async engine and Alembic migrations (`0001` through `0034`).
- **Resilience & Transaction Safety:**
  - **Transactional Outbox Pattern:** Guarantees atomic domain state changes and asynchronous event propagation without dual-write hazards.
  - **Idempotent Consumers:** Inbox pattern with unique deduplication IDs preventing replay issues.
  - **Cryptographic Quote Signing:** HMAC-SHA256 signatures over checkout cart items, prices, and taxes prevent client-side price tampering.
  - **Optimistic Concurrency:** Version-checked inventory reservations preventing overselling during flash events.
- **Frontend Architecture:** Next.js 15 (React 19, TypeScript) utilizing the App Router, Tailwind CSS, Lucide Icons, and accessible Radix UI primitives.

---

## 5. Documented Known Limitations & Roadmap

As this release is prepared for **Round 1 Presentation and Evaluation**, the following ten technical limitations are explicitly documented:

1. **Multilingual Coverage is Partial:** The foundational i18n infrastructure and UI dictionary keys support 12 languages; however, deeper product catalog descriptions, technical specifications, and retailer documents currently remain in English (MC-01).
2. **Razorpay Hosted-Payment Browser Verification Pending:** Automated test coverage and backend webhook HMAC signature verification are fully implemented; final end-to-end browser checkout verification through Razorpay's hosted checkout UI remains pending live production merchant portal credentials.
3. **Database Migration 0034 Pending on Main Dev Database:** Migration `0034` is applied and verified on `basket_demo`; `basket_db` intentionally remains at migration `0033` to prevent schema drift during ongoing audits.
4. **Local Media & Asset Storage:** Product images and KYC identity documents are served from local filesystem storage or external HTTPS URLs; migration to S3-compatible cloud object storage (Cloudflare R2 / AWS S3) with time-limited presigned URLs is planned.
5. **Rule-Based AI Negotiator:** The current deal assistant functions deterministically via rule-based algorithms against retailer floor prices (`mode=rule_based`); full LLM-driven conversational synthesis is reserved for future milestones (MC-07).
6. **OCR Provider Integration Requires Live Adapter:** The handwritten list feature features a complete parsing engine, line confidence scoring, and manual entry fallback; live multi-modal image OCR requires an external cloud vision API key (surfaces typed 503 `OCR_PROVIDER_UNAVAILABLE` when unconfigured, MC-08).
7. **Alembic Cosmetic Schema Drift:** Minor pre-existing discrepancies exist between certain model definitions and historical migration scripts (tracked in `DISCREPANCY_REGISTER.md` MC-09), causing zero functional degradation.
8. **Shared Test Database State Management:** Automated pytest suites must be executed against dedicated test databases (`basket_db_test` or `basket_audit_test`) to prevent test pollution of developer or demo data.
9. **OpenSearch Shared-Index Configuration:** When running the application against standalone demo databases, the backend should be booted with `OPENSEARCH_URL=""` to utilize native PostgreSQL full-text search, avoiding cross-database index pollution (MC-12).
10. **Public Retailer Storefront Functionality:** B2B retailer portals, onboarding, listings, and order fulfillment workflows are fully operational; public customer-facing individual retailer profile storefronts are slated for future release.

---

## 6. Verification & Quality Assurance Summary

Prior to tagging Version 1.0, the platform was verified across all layers:
- **Backend Test Suite:** Fully automated pytest suites validating API contracts, role authorization, inventory safety, order state machines, and Phase 3 modules against isolated test databases.
- **Frontend Verification:** TypeScript compiler type-check passed (`npm run type-check`), ESLint verified (`npm run lint`), unit test suite passed (`npm test`), and production Next.js build completed (`npm run build`).
- **Git State:** Clean working tree, zero uncommitted modifications, and verified local annotated tag `v1.0`.

---
*BASKET Engineering Team — November 2026*
