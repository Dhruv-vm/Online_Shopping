# Basket — Kafka Infrastructure and Real Verification

## Setup
- **Broker:** Kafka 3.7 KRaft in Docker on `127.0.0.1:9094` (PLAINTEXT, localhost only).
- **Topics** (auto-created, 3 partitions):
  - `basket.events.orders`
  - `basket.events.payments`
  - `basket.events.catalogue`
  - `basket.events.inventory`
  - `basket.events.marketplace`
- **Producer:** the transactional outbox publisher (SKIP LOCKED leases, retry with backoff).
- **Consumers:**
  - `basket-order-projection` (orders, payments)
  - `basket-opensearch-sync` (catalogue, inventory)
  - `basket-realtime-<instance>` (all topics, latest offset, for browser notices)
- Idempotency through `consumer_inbox` (consumer_group, event_id).
- `OUTBOX_DISPATCH=direct` (no Kafka) remains available and unchanged.

## Defects found by running against a real broker (all fixed this cycle)

| # | Defect | Effect | Fix |
|---|---|---|---|
| 1 | `partition_assignment_strategy=["cooperative-sticky"]` (a librdkafka/Java name; aiokafka needs classes) | Every group join raised `AttributeError`; **order projection and the search indexer never started** in Kafka mode | Use aiokafka's default assignor; start each consumer independently |
| 2 | **Nothing called `poll_and_process_batch`** in Kafka mode | Consumers joined their groups but **never read an event** (committed offset "-") | `start_consuming()`: a supervised background poll loop, started at app start-up |
| 3 | The Kafka path never built the per-database index, but marked search as ready | Search queried a missing index (404), then fell back | Build the index from PostgreSQL first, then switch search to OpenSearch |
| 4 | `subscribe()` called again after `start()` | Fetcher assertion and an extra rebalance on every start | Subscribe only consumers that were injected |

Earlier phases verified delivery in **direct** mode and with mocks; these defects only showed
up with a live broker.

## Live verification (shared demo, 21 Nov 2026)
- API log:
  - both consumers joined their groups with no fetcher errors;
  - `Search index 'basket_basket_shared_demo_09f0d7_products_write' rebuilt from PostgreSQL (50 products); Kafka indexing active`.
- Retailer price change on "Organic Raw Forest Honey 500g" (₹399 → ₹398):
  - OpenSearch document updated in **1.15 s**;
  - the search API served by `opensearch` showed the new price;
  - the restore propagated too.
- Consumer group `basket-opensearch-sync`: `basket.events.catalogue` partition 1 committed
  offset **4 = log-end 4, lag 0**; `consumer_inbox` holds 4 rows for the group.
- Realtime listener: offer, auction, order, fulfilment and group-buy notices reached browsers in
  0.5–1.3 s (see the realtime report).
- The **order projection consuming a real order event** was not observed separately. Order
  topics showed log-end 0 at the time of the consumer check; the payment-capture path that
  emits `order.confirmed` needs a Razorpay checkout, which was out of scope.

## Tests
`test_final_kafka_consume_loop.py` covers:
- the poll loop runs, survives errors and stops cleanly;
- both production consumers have the loop.

The existing 43 consumer tests still pass. Repeatable live check: `scripts/shared-demo-kafka-check.py`.
