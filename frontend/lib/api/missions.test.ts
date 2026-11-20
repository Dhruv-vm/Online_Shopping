import test from "node:test";
import assert from "node:assert/strict";
import { apiClient, ApiClientError } from "./client.ts";
import type {
  MissionDetail,
  MissionSummary,
  MissionAlternativeItem,
  MissionAddToCartResponse,
} from "@/types";

test("Basket Mission API Client integration", async (t) => {
  const originalFetch = globalThis.fetch;

  t.afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  const mockMissionDetail: MissionDetail = {
    id: "mission-123",
    customer_id: "cust-456",
    title: "Kitchen Setup under ₹15,000",
    description: "Complete cookware and essentials",
    budget_paise: 1500000,
    category_id: "cat-kitchen",
    category_name: "Home & Kitchen",
    people_count: 2,
    preferences: ["durable", "stainless steel"],
    excluded_brands: ["CheapBrand"],
    status: "ACTIVE",
    total_cost_paise: 1420000,
    remaining_budget_paise: 80000,
    is_over_budget: false,
    budget_shortfall_paise: 0,
    items_count: 3,
    unavailable_items_count: 0,
    summary_explanation: "Curated kitchen plan within your budget.",
    groups: [
      {
        group_name: "Cookware",
        subtotal_paise: 1420000,
        items_count: 1,
        items: [
          {
            id: "item-1",
            mission_id: "mission-123",
            product_id: "prod-1",
            variant_id: "var-1",
            listing_id: "list-1",
            retailer_id: "ret-1",
            product_name: "Triply Stainless Steel Kadai",
            brand: "Prestige",
            variant_name: "2.5 Litre",
            sku: "PRESTIGE-TRIPLY-25",
            retailer_name: "Basket Mart",
            retailer_slug: "basket-mart",
            image_url: "https://example.com/kadai.jpg",
            group_name: "Cookware",
            quantity: 1,
            unit_price_paise: 249900,
            current_selling_price_paise: 249900,
            price_changed: false,
            available_stock: 10,
            is_in_stock: true,
            subtotal_paise: 249900,
            is_selected: true,
            recommendation_reason: "Durable stainless steel kadai.",
            sort_order: 0,
          },
        ],
      },
    ],
    items: [],
    created_at: "2026-11-20T00:00:00Z",
    updated_at: "2026-11-20T00:00:00Z",
  };

  await t.test("createMission() posts payload to /api/v1/missions", async () => {
    let capturedUrl: string | undefined;
    let capturedMethod: string | undefined;
    let capturedBody: string | undefined;

    globalThis.fetch = async (input, init) => {
      capturedUrl = String(input);
      capturedMethod = init?.method;
      capturedBody = init?.body as string;
      return new Response(JSON.stringify(mockMissionDetail), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await apiClient.createMission({
      title: "Kitchen Setup under ₹15,000",
      budget_paise: 1500000,
      people_count: 2,
    });

    assert.equal(capturedUrl, "http://localhost:8000/api/v1/missions");
    assert.equal(capturedMethod, "POST");
    assert.ok(capturedBody?.includes("Kitchen Setup under ₹15,000"));
    assert.equal(res.id, "mission-123");
    assert.equal(res.budget_paise, 1500000);
  });

  await t.test("getMissions() requests GET /api/v1/missions", async () => {
    const mockSummaries: MissionSummary[] = [
      {
        id: "mission-123",
        title: "Kitchen Setup under ₹15,000",
        budget_paise: 1500000,
        total_cost_paise: 1420000,
        remaining_budget_paise: 80000,
        is_over_budget: false,
        items_count: 3,
        status: "ACTIVE",
        people_count: 2,
        created_at: "2026-11-20T00:00:00Z",
        updated_at: "2026-11-20T00:00:00Z",
      },
    ];

    globalThis.fetch = async () =>
      new Response(JSON.stringify(mockSummaries), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });

    const res = await apiClient.getMissions();
    assert.equal(res.length, 1);
    assert.equal(res[0].id, "mission-123");
  });

  await t.test("getMission() requests GET /api/v1/missions/{id}", async () => {
    let capturedUrl: string | undefined;

    globalThis.fetch = async (input) => {
      capturedUrl = String(input);
      return new Response(JSON.stringify(mockMissionDetail), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await apiClient.getMission("mission-123");
    assert.equal(capturedUrl, "http://localhost:8000/api/v1/missions/mission-123");
    assert.equal(res.id, "mission-123");
  });

  await t.test("updateMissionItem() sends PATCH to /api/v1/missions/{id}/items/{itemId}", async () => {
    let capturedUrl: string | undefined;
    let capturedMethod: string | undefined;
    let capturedBody: string | undefined;

    globalThis.fetch = async (input, init) => {
      capturedUrl = String(input);
      capturedMethod = init?.method;
      capturedBody = init?.body as string;
      return new Response(JSON.stringify(mockMissionDetail), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    await apiClient.updateMissionItem("mission-123", "item-1", {
      quantity: 2,
      is_selected: false,
    });

    assert.equal(
      capturedUrl,
      "http://localhost:8000/api/v1/missions/mission-123/items/item-1"
    );
    assert.equal(capturedMethod, "PATCH");
    assert.ok(capturedBody?.includes('"quantity":2'));
  });

  await t.test("getMissionItemAlternatives() requests alternatives list", async () => {
    const mockAlts: MissionAlternativeItem[] = [
      {
        listing_id: "list-alt-1",
        product_id: "prod-alt-1",
        variant_id: "var-alt-1",
        product_name: "Hawkins Stainless Steel Frying Pan",
        brand: "Hawkins",
        retailer_id: "ret-2",
        retailer_name: "Basket Lifestyle",
        retailer_slug: "basket-lifestyle",
        selling_price_paise: 219900,
        price_diff_paise: -30000,
        available_stock: 8,
        is_in_stock: true,
        match_type: "CATEGORY_MATCH",
      },
    ];

    globalThis.fetch = async () =>
      new Response(JSON.stringify(mockAlts), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });

    const alts = await apiClient.getMissionItemAlternatives("mission-123", "item-1");
    assert.equal(alts.length, 1);
    assert.equal(alts[0].brand, "Hawkins");
    assert.equal(alts[0].price_diff_paise, -30000);
  });

  await t.test("replaceMissionItem() posts new listing id", async () => {
    let capturedUrl: string | undefined;
    let capturedBody: string | undefined;

    globalThis.fetch = async (input, init) => {
      capturedUrl = String(input);
      capturedBody = init?.body as string;
      return new Response(JSON.stringify(mockMissionDetail), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    await apiClient.replaceMissionItem("mission-123", "item-1", {
      new_listing_id: "list-alt-1",
    });

    assert.equal(
      capturedUrl,
      "http://localhost:8000/api/v1/missions/mission-123/items/item-1/replace"
    );
    assert.ok(capturedBody?.includes("list-alt-1"));
  });

  await t.test("addMissionToCart() posts to add-to-cart endpoint", async () => {
    let capturedUrl: string | undefined;

    const mockCartResp: MissionAddToCartResponse = {
      mission_id: "mission-123",
      added_items_count: 3,
      skipped_items_count: 0,
      warnings: [],
      cart: {},
    };

    globalThis.fetch = async (input) => {
      capturedUrl = String(input);
      return new Response(JSON.stringify(mockCartResp), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await apiClient.addMissionToCart("mission-123");
    assert.equal(
      capturedUrl,
      "http://localhost:8000/api/v1/missions/mission-123/add-to-cart"
    );
    assert.equal(res.added_items_count, 3);
  });

  await t.test("handles ApiClientError on 404 MISSION_NOT_FOUND", async () => {
    globalThis.fetch = async () =>
      new Response(
        JSON.stringify({
          error: {
            code: "MISSION_NOT_FOUND",
            message: "Shopping mission not found.",
          },
        }),
        {
          status: 404,
          headers: { "Content-Type": "application/json" },
        }
      );

    await assert.rejects(
      async () => apiClient.getMission("non-existent"),
      (err: unknown) => {
        assert.ok(err instanceof ApiClientError);
        assert.equal(err.status, 404);
        assert.equal(err.code, "MISSION_NOT_FOUND");
        return true;
      }
    );
  });
});
