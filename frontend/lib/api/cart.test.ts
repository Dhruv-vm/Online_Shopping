import test from "node:test";
import assert from "node:assert/strict";
import { apiClient, ApiClientError } from "./client.ts";
import type { Cart, CartMergeResponse } from "@/types";

test("Universal Shopping Cart API Client integration", async (t) => {
  const originalFetch = globalThis.fetch;

  t.afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  const mockCart: Cart = {
    id: "cart-123",
    status: "ACTIVE",
    currency: "INR",
    items: [
      {
        id: "item-1",
        listing_id: "listing-1",
        variant_id: "var-1",
        product_id: "prod-1",
        product_name: "Noise-Cancelling Headphones",
        product_slug: "noise-cancelling-headphones",
        variant_name: "Midnight Black",
        attributes: { color: "black" },
        primary_image_url: "https://example.com/headphones.jpg",
        retailer_id: "ret-1",
        retailer_name: "Croma Retail",
        retailer_rating: 4.8,
        unit_price_paise: 1999900,
        quantity: 2,
        subtotal_paise: 3999800,
        available_stock: 5,
        is_available: true,
        validation_message: null,
        created_at: "2026-11-17T00:00:00Z",
        updated_at: "2026-11-17T00:00:00Z",
      },
    ],
    item_count: 1,
    total_quantity: 2,
    subtotal_paise: 3999800,
    retailers: [
      {
        retailer_id: "ret-1",
        retailer_name: "Croma Retail",
        item_count: 1,
        subtotal_paise: 3999800,
      },
    ],
    warnings: [],
    created_at: "2026-11-17T00:00:00Z",
    updated_at: "2026-11-17T00:00:00Z",
  };

  await t.test("getCart() requests GET /api/v1/cart and returns Cart", async () => {
    let capturedUrl: string | undefined;
    let capturedCredentials: RequestCredentials | undefined;

    globalThis.fetch = async (input, init) => {
      capturedUrl = input.toString();
      capturedCredentials = init?.credentials;
      return new Response(JSON.stringify(mockCart), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await apiClient.getCart();
    assert.equal(capturedUrl, "http://localhost:8000/api/v1/cart");
    assert.equal(capturedCredentials, "include");
    assert.equal(res.id, "cart-123");
    assert.equal(res.item_count, 1);
    assert.equal(res.total_quantity, 2);
    assert.equal(res.subtotal_paise, 3999800);
    assert.equal(res.items[0].product_name, "Noise-Cancelling Headphones");
  });

  await t.test("addToCart() posts listing_id and quantity to /api/v1/cart/items", async () => {
    let capturedUrl: string | undefined;
    let capturedMethod: string | undefined;
    let capturedBody: string | undefined;

    globalThis.fetch = async (input, init) => {
      capturedUrl = input.toString();
      capturedMethod = init?.method;
      capturedBody = init?.body as string;
      return new Response(JSON.stringify(mockCart), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await apiClient.addToCart("listing-1", 2);
    assert.equal(capturedUrl, "http://localhost:8000/api/v1/cart/items");
    assert.equal(capturedMethod, "POST");
    assert.deepEqual(JSON.parse(capturedBody || "{}"), {
      listing_id: "listing-1",
      quantity: 2,
    });
    assert.equal(res.id, "cart-123");
  });

  await t.test("updateCartItemQuantity() sends PATCH to /api/v1/cart/items/{id}", async () => {
    let capturedUrl: string | undefined;
    let capturedMethod: string | undefined;
    let capturedBody: string | undefined;

    globalThis.fetch = async (input, init) => {
      capturedUrl = input.toString();
      capturedMethod = init?.method;
      capturedBody = init?.body as string;
      return new Response(JSON.stringify({ ...mockCart, total_quantity: 3 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await apiClient.updateCartItemQuantity("item-1", 3);
    assert.equal(capturedUrl, "http://localhost:8000/api/v1/cart/items/item-1");
    assert.equal(capturedMethod, "PATCH");
    assert.deepEqual(JSON.parse(capturedBody || "{}"), { quantity: 3 });
    assert.equal(res.total_quantity, 3);
  });

  await t.test("removeCartItem() sends DELETE to /api/v1/cart/items/{id}", async () => {
    let capturedUrl: string | undefined;
    let capturedMethod: string | undefined;

    globalThis.fetch = async (input, init) => {
      capturedUrl = input.toString();
      capturedMethod = init?.method;
      return new Response(
        JSON.stringify({ ...mockCart, items: [], item_count: 0, total_quantity: 0 }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    };

    const res = await apiClient.removeCartItem("item-1");
    assert.equal(capturedUrl, "http://localhost:8000/api/v1/cart/items/item-1");
    assert.equal(capturedMethod, "DELETE");
    assert.equal(res.item_count, 0);
  });

  await t.test("clearCart() sends DELETE to /api/v1/cart", async () => {
    let capturedUrl: string | undefined;
    let capturedMethod: string | undefined;

    globalThis.fetch = async (input, init) => {
      capturedUrl = input.toString();
      capturedMethod = init?.method;
      return new Response(
        JSON.stringify({ ...mockCart, items: [], item_count: 0, total_quantity: 0 }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    };

    const res = await apiClient.clearCart();
    assert.equal(capturedUrl, "http://localhost:8000/api/v1/cart");
    assert.equal(capturedMethod, "DELETE");
    assert.equal(res.item_count, 0);
  });

  await t.test("mergeCart() posts guest_token to /api/v1/cart/merge", async () => {
    let capturedUrl: string | undefined;
    let capturedMethod: string | undefined;
    let capturedBody: string | undefined;

    const mockMergeResponse: CartMergeResponse = {
      cart: mockCart,
      migrated_items_count: 2,
      warnings: [],
    };

    globalThis.fetch = async (input, init) => {
      capturedUrl = input.toString();
      capturedMethod = init?.method;
      capturedBody = init?.body as string;
      return new Response(JSON.stringify(mockMergeResponse), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await apiClient.mergeCart("guest-token-xyz");
    assert.equal(capturedUrl, "http://localhost:8000/api/v1/cart/merge");
    assert.equal(capturedMethod, "POST");
    assert.deepEqual(JSON.parse(capturedBody || "{}"), {
      guest_token: "guest-token-xyz",
    });
    assert.equal(res.migrated_items_count, 2);
    assert.equal(res.cart.id, "cart-123");
  });

  await t.test("handles ApiClientError on out-of-stock or business errors", async () => {
    globalThis.fetch = async () =>
      new Response(
        JSON.stringify({
          error: {
            code: "INSUFFICIENT_STOCK",
            message: "Only 2 units available in stock.",
          },
        }),
        {
          status: 400,
          headers: { "Content-Type": "application/json" },
        }
      );

    await assert.rejects(
      async () => {
        await apiClient.addToCart("listing-1", 5);
      },
      (err: unknown) => {
        assert(err instanceof ApiClientError);
        assert.equal(err.code, "INSUFFICIENT_STOCK");
        assert.equal(err.status, 400);
        assert.equal(err.message, "Only 2 units available in stock.");
        return true;
      }
    );
  });
});
