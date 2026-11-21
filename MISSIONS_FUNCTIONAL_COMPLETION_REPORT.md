# Missions — Functional Completion Report

**Scope agreed with the owner ("Both"):**
- **Done now:** complete the existing **Basket Mission shopping planner**.
- **Not built:** **reward missions** are a separate feature. They are tracked as
  **NEEDS PRODUCT APPROVAL**, because they need reward rules (what is earned, limits,
  expiry, cost owner). No reward economics were invented or changed.

## Brief checklist, applied to the shopping planner

| Item | Status | Evidence |
|---|---|---|
| Creation | Working (existing) | `POST /missions`: plan from real listings within budget. `test_basket_mission.py::test_customer_create_mission` |
| Eligibility / listing | Working (existing) | Real, in-stock listings only; alternatives and replacement. `test_mission_alternatives_and_replacement` |
| Progress | **Added** | `purchased_items_count` = selected items bought in **paid** orders created after the mission was sent to the cart. Shown on the list card and the detail page. |
| Completion | **Fixed: backend-verified** | Previously `PATCH status=COMPLETED` let the customer self-declare. Now `COMPLETED` is set only in the payment-capture path, when one paid order contains every selected item. The PATCH schema rejects `COMPLETED` (422). |
| Duplicate completion | **Prevented** | Only `ACTIVE`/`SAVED` missions are considered, and rows are locked (`FOR UPDATE SKIP LOCKED`). A second paid order is a no-op. Exactly one `MISSION_COMPLETED` notification. |
| Fraudulent progress | **Prevented** | Progress and completion come from the server's own paid orders, never from client input. An unpaid order never completes a mission. |
| Persistence | Added | `shopping_missions.carted_at`, `completed_at`, `completed_order_id` (migration `0039_mission_completion`, with downgrade). |
| Customer history | Added | Completed missions keep `completed_at` and a link to the completing order. A completed mission can only be archived (other status changes give 409). |
| Expiry | Not applicable | Shopping-planner missions have no expiry. Expiry belongs to reward missions. |
| Reward calculation / issuance | **Not built (needs approval)** | No rewards exist; none are issued. |
| Admin controls | Not applicable to the planner | Reward missions would need admin-defined missions; that is part of the approval item. |

## Flow
1. Create a mission (title, budget, people, preferences).
2. Review the plan; select or deselect items; swap alternatives.
3. **Add to cart.** `carted_at` is recorded; the detail page shows
   "Progress: 0 of N items bought in paid orders".
4. Check out and pay.
5. On capture (`process_payment_capture_and_fulfillment`), `complete_missions_for_order`
   marks the mission `COMPLETED`, stores the order, and sends one in-app notification.

## Tests
`backend/tests/test_final_mission_completion.py`:
- the customer cannot self-complete (422);
- an unpaid order completes nothing;
- a paid order with all items completes exactly once, with one notification;
- a completed mission can only be archived;
- an order missing an item does not complete, and progress shows 1 of 2.

The existing 11 planner tests still pass.

## Reward missions: what approval needs to settle
- Reward type (cashback, coupon, points).
- Value and caps.
- Eligibility, including first-order and fraud rules.
- Expiry.
- Who funds it.
- Reversal on refund or return.
- Admin create, pause and end controls.
- Tax treatment.
