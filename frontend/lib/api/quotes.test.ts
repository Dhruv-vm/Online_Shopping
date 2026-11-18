import test from "node:test";
import assert from "node:assert/strict";
import { apiClient, ApiClientError } from "./client.ts";
import type { Quote, QuoteValidationResult } from "@/types";

test("Quotes & Pricing API Client integration", async (t) => {
  const originalFetch = globalThis.fetch;

  t.afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  const mockQuote: Quote = {
    id: "quote-uuid-123",
    customer_id: "user-uuid-456",
    cart_id: "cart-uuid-789",
    delivery_address_id: "addr-uuid-111",
    delivery_state: "KA",
    subtotal_paise: 118000,
    discount_total_paise: 0,
    delivery_fee_paise: 0,
    cgst_paise: 9000,
    sgst_paise: 9000,
    igst_paise: 0,
    total_tax_paise: 18000,
    total_payable_paise: 118000,
    currency: "INR",
    status: "ACTIVE",
    is_consumed: false,
    consumed_at: null,
    expires_at: "2026-11-17T15:00:00Z",
    superseded_by_quote_id: null,
    created_at: "2026-11-17T14:45:00Z",
    updated_at: "2026-11-17T14:45:00Z",
    items: [
      {
        id: "item-uuid-1",
        listing_id: "listing-uuid-1",
        variant_id: "var-uuid-1",
        retailer_id: "ret-uuid-1",
        product_title: "Sony WH-1000XM5 Headphones",
        variant_title: "Black",
        sku: "SONY-XM5-BLK",
        hsn_code: "8518",
        gst_rate_basis_points: 1800,
        quantity: 1,
        unit_original_price_paise: 1299900,
        unit_selling_price_paise: 118000,
        unit_discount_paise: 0,
        unit_discounted_price_paise: 118000,
        total_selling_price_paise: 118000,
        taxable_base_paise: 100000,
        cgst_paise: 9000,
        sgst_paise: 9000,
        igst_paise: 0,
        total_tax_paise: 18000,
        retailer_name: "Croma",
        retailer_state: "KA",
        created_at: "2026-11-17T14:45:00Z",
      },
    ],
    retailer_breakdowns: [
      {
        retailer_id: "ret-uuid-1",
        retailer_name: "Croma",
        retailer_state: "KA",
        subtotal_paise: 118000,
        delivery_fee_paise: 0,
        free_delivery_threshold_paise: 49900,
        qualifies_for_free_delivery: true,
        amount_needed_for_free_delivery_paise: 0,
      },
    ],
  };

  await t.test("createQuote() posts payload and returns Quote", async () => {
    let capturedUrl: string | undefined;
    let capturedMethod: string | undefined;
    let capturedBody: string | undefined;

    globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
      capturedUrl = input.toString();
      capturedMethod = init?.method;
      capturedBody = init?.body as string;
      return new Response(JSON.stringify(mockQuote), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      });
    }) as typeof fetch;

    const quote = await apiClient.createQuote({
      delivery_address_id: "addr-uuid-111",
      delivery_state: "KA",
    });

    assert.equal(capturedUrl, "http://localhost:8000/api/v1/quotes");
    assert.equal(capturedMethod, "POST");
    assert.deepEqual(JSON.parse(capturedBody || "{}"), {
      delivery_address_id: "addr-uuid-111",
      delivery_state: "KA",
    });
    assert.equal(quote.id, "quote-uuid-123");
    assert.equal(quote.total_payable_paise, 118000);
    assert.equal(quote.items.length, 1);
  });

  await t.test("getQuote() retrieves quote by id", async () => {
    let capturedUrl: string | undefined;

    globalThis.fetch = (async (input: string | URL | Request) => {
      capturedUrl = input.toString();
      return new Response(JSON.stringify(mockQuote), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }) as typeof fetch;

    const quote = await apiClient.getQuote("quote-uuid-123");

    assert.equal(capturedUrl, "http://localhost:8000/api/v1/quotes/quote-uuid-123");
    assert.equal(quote.id, "quote-uuid-123");
  });

  await t.test("validateQuote() returns validation result", async () => {
    const mockValidation: QuoteValidationResult = {
      valid: false,
      reason: "PRICE_CHANGED",
      message: "Quote requires repricing: Price changed.",
      can_refresh: true,
      issues: [
        {
          code: "PRICE_CHANGED",
          message: "Price changed from ₹1,180.00 to ₹1,250.00",
          listing_id: "listing-uuid-1",
        },
      ],
      quote: mockQuote,
    };

    globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
      return new Response(JSON.stringify(mockValidation), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }) as typeof fetch;

    const result = await apiClient.validateQuote("quote-uuid-123");

    assert.equal(result.valid, false);
    assert.equal(result.reason, "PRICE_CHANGED");
    assert.equal(result.can_refresh, true);
    assert.equal(result.issues.length, 1);
  });

  await t.test("refreshQuote() replaces quote and returns new quote", async () => {
    const updatedQuote = { ...mockQuote, id: "quote-uuid-new-999" };

    globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
      return new Response(JSON.stringify(updatedQuote), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      });
    }) as typeof fetch;

    const refreshed = await apiClient.refreshQuote("quote-uuid-123");

    assert.equal(refreshed.id, "quote-uuid-new-999");
  });

  await t.test("listQuotes() returns list of user quotes", async () => {
    globalThis.fetch = (async () => {
      return new Response(JSON.stringify([mockQuote]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }) as typeof fetch;

    const quotes = await apiClient.listQuotes();

    assert.equal(quotes.length, 1);
    assert.equal(quotes[0].id, "quote-uuid-123");
  });

  await t.test("handles ApiClientError on quote not found 404", async () => {
    globalThis.fetch = (async () => {
      return new Response(
        JSON.stringify({
          error: {
            code: "QUOTE_NOT_FOUND",
            message: "Quote not found.",
          },
        }),
        {
          status: 404,
          headers: { "Content-Type": "application/json" },
        }
      );
    }) as typeof fetch;

    await assert.rejects(
      async () => {
        await apiClient.getQuote("nonexistent-quote");
      },
      (err: unknown) => {
        assert(err instanceof ApiClientError);
        assert.equal(err.status, 404);
        assert.equal(err.code, "QUOTE_NOT_FOUND");
        return true;
      }
    );
  });
});
