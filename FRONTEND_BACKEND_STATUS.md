# BASKET — Frontend Architecture & Backend Integration Status

> **Document Version:** 2.0.0  
> **Repository:** `Rahul2006MILLION/Online_Shopping`  
> **Framework:** Next.js 15.5.29 (App Router) | React 19.0.0 | Tailwind CSS v4  
> **Audit Date:** 2026-11-20  
> **Author:** Antigravity Architecture & Reliability Audit Team  

---

## 1. Executive Summary

The BASKET frontend is built on Next.js 15 with React 19, utilizing the App Router architecture with strict TypeScript typing (`npm run type-check` passes cleanly) and Tailwind CSS v4. The application currently comprises **36 routes** across Customer Storefront, Customer Account, Retailer Operations Portal, and Super-Admin Management Portal.

All 36 pages are connected to backend APIs via the typed client `frontend/lib/api.ts`. All 100 frontend unit and component tests (`vitest`) and production compilation (`next build`) pass without warnings or errors.

---

## 2. Route-by-Route Technical Status Matrix

### 2.1 Customer Storefront & Discovery Routes

| Route | File Path | Stakeholder | Backend API Connected | State & Fetch Pattern | Loading / Skeleton | Blinkit Redesign Priority |
| :--- | :--- | :---: | :--- | :--- | :---: | :---: |
| `/` | `app/page.tsx` | Public | `/catalogue/categories`, `/products` | SSR + Client Hydration | Basic skeleton | High (Hero, flash rails) |
| `/categories` | `app/categories/page.tsx` | Public | `/catalogue/categories` | Client fetch with caching | Basic spinner | High (Visual category grid) |
| `/products` | `app/products/page.tsx` | Public | `/catalogue/products`, `/search` | Client query params | Card skeleton | High (Product card shimmer) |
| `/products/[id]`| `app/products/[id]/page.tsx`| Public | `/products/{id}`, `/products/{id}/passport`, `/substitutes` | Dynamic SSR + Client tabs | Tab skeleton | High (PDP layout & badge) |
| `/retailers` | `app/retailers/page.tsx` | Public | `/catalogue/retailers` | Client fetch | Card skeleton | Medium (Nearby shops grid) |
| `/search` | `app/search/page.tsx` | Public | `/search`, `/search/suggestions` | Client dynamic search state | Search skeleton | High (Instant filter pills) |
| `/compare` | `app/compare/page.tsx` | Public | `/substitutes/listings/{id}` | Client local state | Table skeleton | Medium (Side-by-side spec) |

### 2.2 Shopping Cart & Checkout Routes

| Route | File Path | Stakeholder | Backend API Connected | State & Fetch Pattern | Loading / Skeleton | Blinkit Redesign Priority |
| :--- | :--- | :---: | :--- | :--- | :---: | :---: |
| `/cart` | `app/cart/page.tsx` | Guest / Customer | `/cart`, `/cart/items/*`, `/cart/merge` | Client React state + Context | Drawer skeleton | Critical (Sticky cart bar) |
| `/checkout` | `app/checkout/page.tsx` | Customer | `/checkout/quote`, `/reservations`, `/orders`, `/payments` | Multi-step form state | Step shimmer | Critical (Bill breakdown) |
| `/missions` | `app/missions/page.tsx` | Public / Customer | `/missions/thematic`, `/missions/plan` | Client interactive planner | Card skeleton | High (Knapsack visualizer) |
| `/missions/[id]`| `app/missions/[id]/page.tsx`| Customer | `/missions/{id}`, `/missions/sync-to-cart` | Client plan review | List skeleton | High (Budget allocation) |

### 2.3 Order Management & Post-Purchase Routes

| Route | File Path | Stakeholder | Backend API Connected | State & Fetch Pattern | Loading / Skeleton | Blinkit Redesign Priority |
| :--- | :--- | :---: | :--- | :--- | :---: | :---: |
| `/orders` | `app/orders/page.tsx` | Customer | `/orders` | Client fetch | Order card skeleton| High (Delivery status pills) |
| `/orders/[id]` | `app/orders/[id]/page.tsx` | Customer | `/orders/{id}`, `/orders/{id}/returns` | Dynamic SSR + Client modal | Shimmer block | High (Item snapshot cards) |
| `/orders/[id]/track`| `app/orders/[id]/track/page.tsx`| Customer | `/orders/{id}/tracking` | Client polling interval | Stepper skeleton | Critical (Live rider tracker) |

### 2.4 Customer Identity & Intent Memory Routes

| Route | File Path | Stakeholder | Backend API Connected | State & Fetch Pattern | Loading / Skeleton | Blinkit Redesign Priority |
| :--- | :--- | :---: | :--- | :--- | :---: | :---: |
| `/login` | `app/login/page.tsx` | Public | `/auth/login` | Form state + Cookie sync | Button spinner | Medium (Clean OTP/login UI) |
| `/register` | `app/register/page.tsx` | Public | `/auth/register` | Form validation | Button spinner | Medium (Simple signup card) |
| `/register/retailer`| `app/register/retailer/page.tsx`| Public | `/auth/retailer/register` | Multi-step KYC form | Step progress | Medium (Business onboarding) |
| `/account` | `app/account/page.tsx` | Customer | `/users/me` | Client profile state | Shimmer avatar | Medium (Customer menu) |
| `/account/addresses`| `app/account/addresses/page.tsx`| Customer | `/addresses`, `/addresses/{id}` | Form state + Modal | Card skeleton | Medium (Saved address cards) |
| `/account/intent`| `app/account/intent/page.tsx`| Customer | `/intent/overview`, `/intent/profile`, `/intent/consent` | Toggle & chip state | Card skeleton | High (Opt-in toggle card) |

### 2.5 Retailer Portal Routes (`/retailer/*`)

| Route | File Path | Stakeholder | Backend API Connected | State & Fetch Pattern | Loading / Skeleton | Blinkit Redesign Priority |
| :--- | :--- | :---: | :--- | :--- | :---: | :---: |
| `/retailer` | `app/retailer/page.tsx` | Retailer | `/retailer/overview` | Dashboard metrics fetch | Metric card shimmer| Low (B2B Merchant UI) |
| `/retailer/listings`| `app/retailer/listings/page.tsx`| Retailer | `/retailer/listings` | Paginated table state | Table skeleton | Low (Listing management) |
| `/retailer/listings/new`| `app/retailer/listings/new/page.tsx`| Retailer | `/retailer/catalogue/products`, `/retailer/listings` | Multi-step variant picker | Form skeleton | Low (Variant SKU selection)|
| `/retailer/listings/[id]/passport`| `app/retailer/listings/[id]/passport/page.tsx`| Retailer | `/retailer/passport/listings/{id}`, `/retailer/passport/claims` | Form + Claim revision history | Tab skeleton | Low (Claim submission) |
| `/retailer/inventory`| `app/retailer/inventory/page.tsx`| Retailer | `/retailer/inventory`, `/retailer/inventory/bulk-adjust` | Editable table state | Table skeleton | Low (Stock inline edit) |
| `/retailer/orders` | `app/retailer/orders/page.tsx` | Retailer | `/retailer/orders`, `/retailer/orders/{id}/status` | Order dispatch list | Table skeleton | Low (Fulfillment queue) |
| `/retailer/offers` | `app/retailer/offers/page.tsx` | Retailer | `/retailer/offers` | Campaign list state | Card skeleton | Low (Discount campaigns) |
| `/retailer/analytics`| `app/retailer/analytics/page.tsx`| Retailer | `/retailer/analytics` | Chart data fetch | Chart skeleton | Low (Sales charts) |
| `/retailer/profile`| `app/retailer/profile/page.tsx`| Retailer | `/retailer/profile` | Store information form | Form skeleton | Low (KYC details) |
| `/retailer/settings`| `app/retailer/settings/page.tsx`| Retailer | `/retailer/profile` | Store settings form | Form skeleton | Low (Store toggle) |

### 2.6 Administrator Portal Routes (`/admin/*`)

| Route | File Path | Stakeholder | Backend API Connected | State & Fetch Pattern | Loading / Skeleton | Blinkit Redesign Priority |
| :--- | :--- | :---: | :--- | :--- | :---: | :---: |
| `/admin` | `app/admin/page.tsx` | Admin | `/admin/overview` | Platform KPI cards fetch | Metric shimmer | Low (Admin operations) |
| `/admin/retailers` | `app/admin/retailers/page.tsx` | Admin | `/admin/retailers` | Verification table state | Table skeleton | Low (Retailer audit table)|
| `/admin/retailers/[id]`| `app/admin/retailers/[id]/page.tsx`| Admin | `/admin/retailers/{id}`, `/admin/retailers/{id}/verify` | Document review view | Card skeleton | Low (GSTIN/PAN approval) |
| `/admin/catalogue` | `app/admin/catalogue/page.tsx` | Admin | `/admin/catalogue/categories`, `/admin/catalogue/products` | Taxonomy management tree | Tree skeleton | Low (Global taxonomy) |
| `/admin/deals` | `app/admin/deals/page.tsx` | Admin | `/admin/deals` | Deals creation form | Table skeleton | Low (Platform deals) |
| `/admin/passport` | `app/admin/passport/page.tsx` | Admin | `/admin/passport/queue`, `/admin/passport/claims/{id}/verify`| Moderation queue table | Queue skeleton | Low (Claim verification) |

---

## 3. Frontend Architecture & Design System Guidelines

### 3.1 Upcoming Blinkit-Inspired Redesign Specifications
For the upcoming frontend visual refresh, the application must transition to a modern, vibrant, quick-commerce aesthetic inspired by **Blinkit**:
- **Brand Palette:**
  - Primary Yellow: `#F8CB46` / `#FFDE59` (Vibrant accent, CTA badges, delivery guarantee)
  - Primary Green: `#0C831F` / `#00A859` (Add to cart buttons, pricing highlights, stock status, verified badges)
  - Dark Charcoal: `#1C1C1C` / `#222222` (High-contrast typography)
  - Soft Background: `#F4F6F8` (Crisp contrast against white product cards)
- **Brand Identity Rule:**
  - Preserve the existing **BASKET** logo mark and brand name. Do not rename the application.
- **Micro-Interactions & Animation System:**
  - Add to Cart Bounce: Subtle scale bounce (`transform: scale(1.05)`) when incrementing/decrementing quantities.
  - Floating Sticky Cart: Mobile-first bottom drawer pill displaying total items and order amount with an arrow CTA.
  - Shimmer Loading System: Standardized `animate-pulse` shimmer skeletons across all product cards, category carousels, and checkout summary blocks.
- **Image Optimization & Aspect Ratios:**
  - Enforce Next.js `<Image />` component with configured responsive sizes and blur placeholders to eliminate layout shift (CLS).
  - Consistent 1:1 square ratio for product catalogue cards.

---

## 4. Verification & Build Integrity

```bash
# Verify TypeScript strict compile
npm run type-check

# Verify ESLint code standards
npm run lint

# Verify full 100 frontend test suite
npm test

# Verify production Next.js compilation (36 routes)
npm run build
```
Result: All 36 routes statically optimized or dynamically rendered with 0 compile errors.
