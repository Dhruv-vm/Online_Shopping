import test from "node:test";
import assert from "node:assert/strict";
import { ApiClientError } from "./client.ts";
import * as p3 from "./phase3.ts";

type Captured = { url: string; method: string; body: unknown };

function mockFetch(response: unknown, status = 200): Captured[] {
  const calls: Captured[] = [];
  globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    calls.push({
      url: String(input),
      method: init?.method ?? "GET",
      body: init?.body ? JSON.parse(String(init.body)) : undefined,
    });
    return new Response(status === 204 ? null : JSON.stringify(response), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  };
  return calls;
}

test("Phase 3 API client", async (t) => {
  const original = globalThis.fetch;
  t.afterEach(() => {
    globalThis.fetch = original;
  });

  await t.test("price intelligence GET with window", async () => {
    const calls = mockFetch({ badge: "GENUINE_DISCOUNT", history: [] });
    const r = await p3.getPriceIntelligence("lst-1", 30);
    assert.equal(r.badge, "GENUINE_DISCOUNT");
    assert.equal(calls[0].url, "http://localhost:8000/api/v1/price-intelligence/listings/lst-1?days=30");
  });

  await t.test("sale stream polling with since cursor", async () => {
    const calls = mockFetch({ items: [], next_cursor: null, server_time: "t", poll_after_seconds: 15 });
    await p3.getSaleStream({ event_type: "FLASH_DEAL", since: "2026-11-20T10:00:00Z" });
    assert.ok(calls[0].url.endsWith("/api/v1/sale-stream/live?event_type=FLASH_DEAL&since=2026-11-20T10%3A00%3A00Z"));
  });

  await t.test("language preference PUT", async () => {
    const calls = mockFetch({ language: "ta" });
    await p3.setLanguagePreference("ta");
    assert.deepEqual([calls[0].method, calls[0].body], ["PUT", { language: "ta" }]);
  });

  await t.test("translations bulk GET joins ids", async () => {
    const calls = mockFetch({ entity_type: "product", language: "hi", translations: {} });
    await p3.getTranslations("product", ["a", "b"], "hi");
    assert.ok(calls[0].url.includes("ids=a%2Cb") && calls[0].url.includes("lang=hi"));
  });

  await t.test("demand signal and retailer fulfil", async () => {
    let calls = mockFetch({ pool: { id: "p1" }, deduplicated: false }, 201);
    await p3.logDemandSignal({ query_text: "kahwa", pincode: "560001" });
    assert.deepEqual([calls[0].method, calls[0].url.split("8000")[1]], ["POST", "/api/v1/demand/signal"]);
    calls = mockFetch({ id: "p1" });
    await p3.retailerFulfillDemand("p1", "l1", "Stocked");
    assert.deepEqual(calls[0].body, { listing_id: "l1", note: "Stocked" });
  });

  await t.test("community buying join and share", async () => {
    let calls = mockFetch({ id: "c1" });
    await p3.joinCampaign("c1", 2);
    assert.deepEqual([calls[0].url.split("8000")[1], calls[0].body], ["/api/v1/community-buying/campaigns/c1/join", { quantity: 2 }]);
    calls = mockFetch({ url: "u", message: "m", whatsapp_url: "w", sms_url: "s" });
    const s = await p3.shareCampaign("c1");
    assert.equal(s.whatsapp_url, "w");
  });

  await t.test("RFQ create, bid and accept", async () => {
    let calls = mockFetch({ id: "r1" }, 201);
    await p3.createRfq({ title: "Party", delivery_pincode: "560034", items: [{ name: "Rice", quantity: 2 }] });
    assert.equal((calls[0].body as { items: unknown[] }).items.length, 1);
    calls = mockFetch({ id: "b1" }, 201);
    await p3.retailerSubmitRfqBid("r1", { lines: [{ manifest_index: 0, listing_id: "l", unit_price_paise: 100 }], estimated_delivery_hours: 4 });
    assert.equal(calls[0].url.split("8000")[1], "/api/v1/retailer/exchange/requests/r1/bids");
    calls = mockFetch({ request: { id: "r1" }, cart_id: "c", awarded_lines: 1, message: "ok" });
    await p3.acceptRfqBid("r1", "b1");
    assert.deepEqual(calls[0].body, { bid_id: "b1" });
  });

  await t.test("negotiation counter-offer and accept", async () => {
    let calls = mockFetch({ id: "s1", status: "IN_PROGRESS" });
    await p3.counterOffer("s1", 90000);
    assert.deepEqual(calls[0].body, { session_id: "s1", proposed_price_paise: 90000 });
    calls = mockFetch({ id: "s1", status: "ACCEPTED", quote_id: "q1" });
    const s = await p3.acceptNegotiation("s1");
    assert.equal(s.quote_id, "q1");
  });

  await t.test("auction start, retailer bid and accept", async () => {
    let calls = mockFetch({ id: "a1", status: "ACTIVE" }, 201);
    await p3.startAuction("400001");
    assert.deepEqual(calls[0].body, { pincode: "400001" });
    calls = mockFetch({ id: "b1" }, 201);
    await p3.retailerBid("a1", { bid_price_paise: 90000, delivery_eta_minutes: 15 });
    assert.equal(calls[0].url.split("8000")[1], "/api/v1/retailer/auctions/a1/bid");
    calls = mockFetch({ auction: { id: "a1" }, cart_id: "c", message: "m" });
    await p3.acceptAuctionBid("a1", "b1");
    assert.deepEqual(calls[0].body, { bid_id: "b1" });
  });

  await t.test("vision parse-list surfaces OCR_PROVIDER_UNAVAILABLE", async () => {
    mockFetch({ error: { code: "OCR_PROVIDER_UNAVAILABLE", message: "not configured" } }, 503);
    await assert.rejects(
      () => p3.parseShoppingList({ image_base64: "AAAA", content_type: "image/png" }),
      (err: unknown) => err instanceof ApiClientError && err.code === "OCR_PROVIDER_UNAVAILABLE" && err.status === 503,
    );
  });

  await t.test("build cart from reviewed list", async () => {
    const calls = mockFetch({ cart_id: "c", added: 1, skipped: [] });
    await p3.buildCartFromList([{ listing_id: "l1", quantity: 3 }]);
    assert.deepEqual(calls[0].body, { items: [{ listing_id: "l1", quantity: 3 }] });
  });
});
