import test from "node:test";
import assert from "node:assert/strict";
import { apiClient, ApiClientError } from "./client.ts";
import { reservationApi } from "./reservations.ts";
import type { Reservation, ReservationReleaseResponse } from "../../types/index.ts";

test("Inventory Reservations API Client integration", async (t) => {
  const originalFetch = globalThis.fetch;

  t.afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  const mockReservation: Reservation = {
    id: "res-uuid-123",
    quote_id: "quote-uuid-456",
    customer_id: "user-uuid-789",
    status: "ACTIVE",
    idempotency_key: "idem-key-abc",
    expires_at: "2026-11-17T15:10:00Z",
    seconds_remaining: 600,
    is_expired: false,
    created_at: "2026-11-17T15:00:00Z",
    updated_at: "2026-11-17T15:00:00Z",
    items: [
      {
        id: "item-uuid-1",
        listing_id: "listing-uuid-1",
        retailer_id: "ret-uuid-1",
        variant_id: "var-uuid-1",
        quantity: 2,
      },
    ],
  };

  await t.test("createReservation() posts quote_id and optional idempotency key", async () => {
    let capturedUrl = "";
    let capturedOptions: RequestInit | undefined;

    globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      capturedUrl = input.toString();
      capturedOptions = init;
      return new Response(JSON.stringify(mockReservation), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await reservationApi.createReservation(
      { quote_id: "quote-uuid-456" },
      "test-idem-key"
    );

    assert.equal(capturedUrl, "http://localhost:8000/api/v1/reservations");
    assert.equal(capturedOptions?.method, "POST");
    assert.deepEqual(JSON.parse(capturedOptions?.body as string), {
      quote_id: "quote-uuid-456",
    });

    const headers = capturedOptions?.headers as Record<string, string>;
    assert.equal(headers["Idempotency-Key"], "test-idem-key");
    assert.equal(res.id, "res-uuid-123");
    assert.equal(res.status, "ACTIVE");
    assert.equal(res.seconds_remaining, 600);
    assert.equal(res.items.length, 1);
  });

  await t.test("getReservation() fetches reservation by id", async () => {
    let capturedUrl = "";

    globalThis.fetch = async (input: RequestInfo | URL) => {
      capturedUrl = input.toString();
      return new Response(JSON.stringify(mockReservation), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await reservationApi.getReservation("res-uuid-123");
    assert.equal(
      capturedUrl,
      "http://localhost:8000/api/v1/reservations/res-uuid-123"
    );
    assert.equal(res.id, "res-uuid-123");
    assert.equal(res.is_expired, false);
  });

  await t.test("releaseReservation() posts to release endpoint", async () => {
    let capturedUrl = "";
    let capturedOptions: RequestInit | undefined;

    const mockRelease: ReservationReleaseResponse = {
      id: "res-uuid-123",
      status: "RELEASED",
      released_at: "2026-11-17T15:05:00Z",
      release_reason: "USER_RELEASED",
    };

    globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      capturedUrl = input.toString();
      capturedOptions = init;
      return new Response(JSON.stringify(mockRelease), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await reservationApi.releaseReservation("res-uuid-123");
    assert.equal(
      capturedUrl,
      "http://localhost:8000/api/v1/reservations/res-uuid-123/release"
    );
    assert.equal(capturedOptions?.method, "POST");
    assert.equal(res.status, "RELEASED");
    assert.equal(res.release_reason, "USER_RELEASED");
  });

  await t.test("createReservation() throws ApiClientError on 409 INSUFFICIENT_STOCK", async () => {
    const errorBody = {
      error: {
        code: "INSUFFICIENT_STOCK",
        message: "One or more items do not have sufficient stock.",
        request_id: "req-err-409",
        details: [
          {
            listing_id: "listing-uuid-1",
            product_title: "Sony WH-1000XM5",
            requested_quantity: 2,
            available_quantity: 1,
            message: "Insufficient stock for Sony WH-1000XM5.",
          },
        ],
      },
    };

    globalThis.fetch = async () => {
      return new Response(JSON.stringify(errorBody), {
        status: 409,
        headers: { "Content-Type": "application/json" },
      });
    };

    await assert.rejects(
      async () => {
        await reservationApi.createReservation({ quote_id: "quote-uuid-456" });
      },
      (err: unknown) => {
        assert(err instanceof ApiClientError);
        assert.equal(err.status, 409);
        assert.equal(err.code, "INSUFFICIENT_STOCK");
        assert.equal(err.message, "One or more items do not have sufficient stock.");
        assert.equal(err.details.length, 1);
        return true;
      }
    );
  });

  await t.test("createReservation() throws ApiClientError on 409 QUOTE_EXPIRED", async () => {
    const errorBody = {
      error: {
        code: "QUOTE_EXPIRED",
        message: "Quote validity has elapsed. Please refresh your quote before reserving inventory.",
        request_id: "req-err-exp",
      },
    };

    globalThis.fetch = async () => {
      return new Response(JSON.stringify(errorBody), {
        status: 409,
        headers: { "Content-Type": "application/json" },
      });
    };

    await assert.rejects(
      async () => {
        await reservationApi.createReservation({ quote_id: "quote-uuid-expired" });
      },
      (err: unknown) => {
        assert(err instanceof ApiClientError);
        assert.equal(err.status, 409);
        assert.equal(err.code, "QUOTE_EXPIRED");
        return true;
      }
    );
  });

  await t.test("getReservation() throws ApiClientError on 404 RESERVATION_NOT_FOUND", async () => {
    const errorBody = {
      error: {
        code: "RESERVATION_NOT_FOUND",
        message: "Reservation was not found.",
        request_id: "req-err-404",
      },
    };

    globalThis.fetch = async () => {
      return new Response(JSON.stringify(errorBody), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      });
    };

    await assert.rejects(
      async () => {
        await reservationApi.getReservation("res-unknown");
      },
      (err: unknown) => {
        assert(err instanceof ApiClientError);
        assert.equal(err.status, 404);
        assert.equal(err.code, "RESERVATION_NOT_FOUND");
        return true;
      }
    );
  });
});
