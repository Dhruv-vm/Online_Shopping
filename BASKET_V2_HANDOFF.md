# BASKET — Version 2.0 Engineering Handoff to Branding & UI/UX Phase

**Handoff From:** Core Backend & Platform Engineering  
**Handoff To:** Design, Branding, and UI/UX Specialists  
**Branch:** `feature/version-2-development`  
**Baseline Git Tag (Historical):** `v1.0` (Preserved and untouched)  
**Proposed Release Tag:** `v2.0`  
**Date:** November 2026  

---

## 1. Handoff Objectives & Scope Boundaries

Core engineering for BASKET Version 2.0 is functionally complete. The application is now entering a dedicated **Branding, UI, and UX Phase**.

### ⚠️ Strict Rules for the Branding & UI/UX Phase:
1. **Preserve Functional Logic:** Do not modify API routes, Pydantic schemas, database models, or payment orchestration logic.
2. **Preserve Data Contracts:** When styling forms and buttons, preserve exact field names, data types, and action handlers.
3. **No Database Migrations without Architecture Approval:** Keep Alembic head at `0039_mission_completion`.
4. **Preserve Quality Gates:** All 604 backend tests and 129 frontend tests must remain passing on every PR.

---

## 2. Frontend Architecture & Technology Baseline

- **Framework:** Next.js 15.5.29 (App Router) on Node.js 22 LTS.
- **Styling Engine:** Tailwind CSS v4.
- **Component Primitives:** Radix UI accessible UI primitives.
- **Icons:** Lucide React (`lucide-react`).
- **State Management:** React 19 Contexts (`auth-context.tsx`, `cart-context.tsx`, `i18n-context.tsx`).
- **Real-Time Client:** Server-Sent Events client (`lib/realtime.ts`) with focus-refresh and automatic reconnection.

---

## 3. Key Frontend Directory Mapping

```text
frontend/
├── app/
│   ├── (storefront)/         # Home, category lists, product detail (/products/[id])
│   ├── account/              # Customer profile, addresses, intent (/account/intent), recurring
│   ├── admin/                # Admin governance, retailer review, deals, demand gaps, audit
│   ├── cart/                 # Customer shopping basket with coupon validation
│   ├── checkout/             # Order checkout, address selection, payment launch
│   ├── community-buying/     # Group purchasing & WhatsApp referral links
│   ├── missions/             # Basket Shopping Missions
│   ├── orders/               # Order history, timeline, tracking, returns
│   ├── retailer/             # Retailer portal, inventory, auctions, orders, onboarding
│   └── search/               # Search results page with faceted category filters
├── components/
│   ├── catalogue/            # Product cards, grids, filters
│   ├── intent/               # Intent workflow cards
│   ├── shared/               # Global Header, Footer, Language Picker, Notification Bell
│   └── ui/                   # Core buttons, dialogs, inputs, tabs, badges
└── lib/
    ├── api/                  # Centralized typed API clients
    ├── i18n/                 # Dictionaries and locale formatters
    └── realtime.ts           # Shared SSE event stream
```

---

## 4. Current Design System Baseline (Frozen Baseline)

- **Primary Brand Palette:** Emerald green (`emerald-600` / `emerald-700`) paired with amber / warm yellow accents (`amber-500`).
- **Neutral Backgrounds:** Crisp off-white backgrounds with soft border card boundaries (`border-border`, `bg-card`).
- **Typography:** Modern clean sans-serif system font stack with high contrast ratio.
- **Role Theming:** Subtly differentiated accent lines across Customer, Retailer, and Admin consoles.

The incoming Branding team is authorized to iterate on typography, palette harmony, whitespace, micro-interactions, mobile responsive layout polish, and brand iconography while maintaining the structural page routes and data hooks.

---

## 5. Verification Commands for Designers & Frontend Developers

Before committing any UI or styling changes, always run the validation suite:

```bash
cd frontend
npm test                # 129 tests must pass
npm run type-check      # TypeScript must be 100% clean
npm run lint            # ESLint checks must pass
npm run build           # All 56 routes must compile cleanly
```
