import test from "node:test";
import assert from "node:assert/strict";
import { apiClient, ApiClientError } from "./client.ts";
import type {
  SubstituteListResponse,
  CartItemReplaceResponse,
  Cart,
} from "@/types";

test("Basket Substitute Intelligence API Client integration", async (t) => {
  const originalFetch = globalThis.fetch;

  t.afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  const mockSubstituteList: SubstituteListResponse = {
    original_listing_id: "listing-orig",
    original_product_name: "Apple iPhone 15",
    original_product_slug: "apple-iphone-15",
    original_brand: "Apple",
    original_category_id: "cat-phones",
    original_category_name: "Smartphones",
    original_selling_price_paise: 7000000,
    original_is_in_stock: true,
    original_available_stock: 5,
    original_attributes: { storage: "128GB", ram: "6GB", color: "Blue" },
    total_count: 2,
    trigger_reason: "EXPLORE",
    substitutes: [
      {
        listing_id: "listing-sub-1",
        product_id: "prod-sub-1",
        product_name: "Apple iPhone 15 (Black)",
        product_slug: "apple-iphone-15-black",
        brand: "Apple",
        variant_id: "var-sub-1",
        variant_name: "Black 128GB",
        variant_sku: "SKU-BLK-128",
        variant_attributes: { storage: "128GB", ram: "6GB", color: "Black" },
        primary_image_url: "https://example.com/iphone-black.jpg",
        retailer_id: "ret-2",
        retailer_name: "Beta Retailer",
        retailer_slug: "beta-retailer",
        retailer_rating: 4.8,
        retailer_verification_status: "VERIFIED",
        original_price_paise: 7990000,
        selling_price_paise: 6950000,
        price_diff_paise: -50000,
        price_diff_percentage: -0.7,
        savings_percentage: 0.7,
        available_stock: 12,
        is_in_stock: true,
        availability_status: "IN_STOCK",
        similarity_score: 0.88,
        substitute_type: "CLOSEST_MATCH",
        applicable_types: ["CLOSEST_MATCH", "BETTER_VALUE"],
        reason: "Closest match with matching brand and core specs.",
        matching_specs: ["Brand: Apple", "Storage: 128GB", "Ram: 6GB"],
        differing_specs: ["Color: Black (was Blue)"],
        detailed_comparisons: [
          {
            attribute_key: "brand",
            label: "Brand",
            original_value: "Apple",
            substitute_value: "Apple",
            is_match: true,
          },
        ],
        compatibility_notes: "Direct drop-in replacement in the same category.",
      },
      {
        listing_id: "listing-sub-2",
        product_id: "prod-sub-2",
        product_name: "Samsung Galaxy S23",
        product_slug: "samsung-galaxy-s23",
        brand: "Samsung",
        variant_id: "var-sub-2",
        variant_name: "Cream 128GB",
        variant_sku: "SKU-SAM-128",
        variant_attributes: { storage: "128GB", ram: "8GB", color: "Cream" },
        primary_image_url: "https://example.com/galaxy.jpg",
        retailer_id: "ret-1",
        retailer_name: "Alpha Store",
        retailer_slug: "alpha-store",
        retailer_rating: 4.9,
        retailer_verification_status: "VERIFIED",
        original_price_paise: 7499000,
        selling_price_paise: 5500000,
        price_diff_paise: -1500000,
        price_diff_percentage: -21.4,
        savings_percentage: 21.4,
        available_stock: 20,
        is_in_stock: true,
        availability_status: "IN_STOCK",
        similarity_score: 0.65,
        substitute_type: "BUDGET_FRIENDLY",
        applicable_types: ["BUDGET_FRIENDLY", "BETTER_VALUE"],
        reason: "Save ₹1500.00 (21.4% off) with equivalent core specifications.",
        matching_specs: ["Storage: 128GB"],
        differing_specs: ["Brand: Samsung (was Apple)", "Color: Cream (was Blue)"],
        detailed_comparisons: [],
        compatibility_notes: "Compatible within Smartphones.",
      },
    ],
  };

  const mockCart: Cart = {
    id: "cart-1",
    status: "ACTIVE",
    currency: "INR",
    items: [],
    item_count: 0,
    total_quantity: 0,
    subtotal_paise: 0,
    retailers: [],
    warnings: [],
    created_at: "2026-11-20T00:00:00Z",
    updated_at: "2026-11-20T00:00:00Z",
  };

  await t.test(
    "getListingSubstitutes() sends GET /api/v1/substitutes/listings/{id} with query params",
    async () => {
      let capturedUrl = "";
      globalThis.fetch = (async (url: string | URL | Request) => {
        capturedUrl = url.toString();
        return new Response(JSON.stringify(mockSubstituteList), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }) as typeof fetch;

      const res = await apiClient.getListingSubstitutes("listing-orig", {
        type: "BUDGET_FRIENDLY",
        limit: 5,
        in_stock_only: true,
      });

      assert.equal(res.original_listing_id, "listing-orig");
      assert.equal(res.substitutes.length, 2);
      assert.ok(
        capturedUrl.includes("/api/v1/substitutes/listings/listing-orig")
      );
      assert.ok(capturedUrl.includes("type=BUDGET_FRIENDLY"));
      assert.ok(capturedUrl.includes("limit=5"));
      assert.ok(capturedUrl.includes("in_stock_only=true"));
    }
  );

  await t.test(
    "getCartItemSubstitutes() sends GET /api/v1/cart/items/{itemId}/substitutes",
    async () => {
      let capturedUrl = "";
      globalThis.fetch = (async (url: string | URL | Request) => {
        capturedUrl = url.toString();
        return new Response(JSON.stringify(mockSubstituteList), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }) as typeof fetch;

      const res = await apiClient.getCartItemSubstitutes("cart-item-123");

      assert.equal(res.original_listing_id, "listing-orig");
      assert.ok(
        capturedUrl.includes("/api/v1/cart/items/cart-item-123/substitutes")
      );
    }
  );

  await t.test(
    "replaceCartItem() sends POST /api/v1/cart/items/{itemId}/replace",
    async () => {
      let capturedUrl = "";
      let capturedBody = "";
      const mockReplaceResponse: CartItemReplaceResponse = {
        cart: mockCart,
        replaced_item_id: "item-old",
        new_item_id: "item-new",
        message: "Item successfully replaced in your basket.",
      };

      globalThis.fetch = (async (
        url: string | URL | Request,
        init?: RequestInit
      ) => {
        capturedUrl = url.toString();
        capturedBody = init?.body as string;
        return new Response(JSON.stringify(mockReplaceResponse), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }) as typeof fetch;

      const res = await apiClient.replaceCartItem("item-old", {
        new_listing_id: "listing-sub-1",
        quantity: 2,
      });

      assert.equal(res.replaced_item_id, "item-old");
      assert.equal(res.new_item_id, "item-new");
      assert.ok(capturedUrl.includes("/api/v1/cart/items/item-old/replace"));
      const body = JSON.parse(capturedBody);
      assert.equal(body.new_listing_id, "listing-sub-1");
      assert.equal(body.quantity, 2);
    }
  );

  await t.test(
    "replaceCartItem() handles ApiClientError on CATEGORY_MISMATCH or OUT_OF_STOCK",
    async () => {
      globalThis.fetch = (async () => {
        return new Response(
          JSON.stringify({
            error: {
              code: "CATEGORY_MISMATCH",
              message: "Substitute product must belong to the same category.",
            },
          }),
          {
            status: 400,
            headers: { "Content-Type": "application/json" },
          }
        );
      }) as typeof fetch;

      await assert.rejects(
        async () => {
          await apiClient.replaceCartItem("item-1", {
            new_listing_id: "invalid-listing",
          });
        },
        (err: unknown) => {
          assert.ok(err instanceof ApiClientError);
          assert.equal(err.code, "CATEGORY_MISMATCH");
          assert.equal(err.status, 400);
          return true;
        }
      );
    }
  );
});
