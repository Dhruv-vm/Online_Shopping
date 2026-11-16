# BASKET — Shared Agent Handoff & Conversation Log

> This is the coordination document between Developer A, Developer B, and their Antigravity agents. It is not a place for vague status updates. Record decisions, requests, blockers, and integration notes so the other developer can continue without guessing.

## 1. Rules for using this file

- Append a new entry; do not silently rewrite or delete another person's entry.
- Use timestamps in IST (`YYYY-MM-DD HH:MM IST`).
- Identify the author: `Developer A`, `Developer B`, or `Integration Owner`.
- Every request must state what response/action is needed and by when.
- Every shared API/schema change must be written here before implementation.
- The receiving developer must reply in a new entry with `ACCEPTED`, `REJECTED`, or `NEEDS DISCUSSION`.
- A handoff is not approval to merge. GitHub PR review is still required.
- Keep entries concise, factual, and actionable.
- Do not paste secrets, tokens, private customer data, or huge logs. Link to a sanitized log or PR instead.

## 2. Current team ownership

| Area | Owner | Backup/reviewer |
|---|---|---|
| Integration branch and shared contracts | To be assigned | Other developer |
| Frontend foundation | Developer A/B — decide together | Other developer |
| Backend foundation and DB migrations | Developer A/B — decide together | Other developer |
| Catalogue/search | To be assigned | To be assigned |
| Cart/checkout/orders | To be assigned | To be assigned |
| Kafka/outbox/workers | To be assigned | To be assigned |
| Optional differentiators | To be assigned | To be assigned |

Fill this table before parallel implementation.

## 3. Current shared baseline

- Base branch: `integration` (create if it does not exist).
- Stable branch: `main`.
- Stack: Next.js + TypeScript; FastAPI + SQLAlchemy 2 + Alembic; Aiven PostgreSQL, Kafka, OpenSearch.
- API prefix: `/api/v1`.
- Database authority: PostgreSQL.
- Search authority: OpenSearch only for retrieval, never checkout validation.
- Event publication: transactional outbox.
- Payment: Razorpay Sandbox only when configured and server-verified.

## 4. Entry template — proposal/request

Copy this section for every new request.

### [YYYY-MM-DD HH:MM IST] — [AUTHOR] — [PROPOSAL / REQUEST / BLOCKER]

**Related branch / PR / task:**  
**Affected module(s):**  
**What I am proposing or requesting:**  
**Reason:**  
**Files/contracts affected:**  
**Backward compatibility impact:**  
**What I need from the other developer:**  
**Required response by:**  

**Status:** OPEN

---

## 5. Entry template — response

### [YYYY-MM-DD HH:MM IST] — [AUTHOR] — [RESPONSE]

**Replying to:**  
**Decision:** ACCEPTED / REJECTED / NEEDS DISCUSSION  
**Reason:**  
**Required follow-up:**  
**Owner:**  
**Status:** OPEN / RESOLVED

---

## 6. Entry template — implementation handoff

### [YYYY-MM-DD HH:MM IST] — [AUTHOR] — [IMPLEMENTATION HANDOFF]

**Task:**  
**Branch / PR:**  
**What is implemented:**  
**Files changed:**  
**API/schema/event changes:**  
**Migration details:**  
**Tests and results:**  
**Known limitations:**  
**How to run or verify:**  
**What the next developer should do:**  

**Status:** READY FOR REVIEW / BLOCKED / NEEDS FOLLOW-UP

---

## 7. Integration incident template

### [YYYY-MM-DD HH:MM IST] — [AUTHOR] — [INTEGRATION INCIDENT]

**Observed failure:**  
**Steps to reproduce:**  
**Expected behaviour:**  
**Actual behaviour:**  
**Relevant branch/commit/PR:**  
**Logs (sanitized):**  
**Suspected owner/module:**  
**Immediate containment:**  
**Resolution:**  

**Status:** OPEN / RESOLVED

---

## 8. Live log

No entries yet. Add the first entry when the team assigns ownership and agrees on the shared foundation.
