import test from "node:test";
import assert from "node:assert/strict";
import { apiClient, ApiClientError } from "./client.ts";
import { createOrder, getOrder, listOrders, orderApi } from "./orders.ts";
import type { Order, OrderListResponse } from "../../types/index.ts";

test("Orders API Client integration", async (t) => {
  const originalFetch = globalThis.fetch;

  t.afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  const mockOrder: Order = {
    id: "ord-uuid-123",
    order_number: "BSK-20261117-ABC123",
    customer_id: "usr-uuid-456",
    is_guest: false,
    quote_id: "quo-uuid-789",
    reservation_id: "res-uuid-101",
    delivery_address: {
      full_name: "Rahul Verma",
      address_line1: "123 Indiranagar 100ft Road",
      address_line2: "Apt 4B",
      city: "Bengaluru",
      state: "Karnataka",
      postal_code: "560038",
      phone: "+919876543210",
    },
    subtotal_paise: 100000,
    discount_total_paise: 10000,
    delivery_fee_paise: 5000,
    cgst_paise: 8100,
    sgst_paise: 8100,
    igst_paise: 0,
    total_tax_paise: 16200,
    total_payable_paise: 111200,
    currency: "INR",
    status: "PENDING_PAYMENT",
    payment_status: "NOT_INITIATED",
    payment_window_expires_at: "2026-11-17T15:15:00Z",
    items: [
      {
        id: "item-uuid-1",
        listing_id: "list-uuid-1",
        variant_id: "var-uuid-1",
        retailer_id: "ret-uuid-1",
        product_title: "Ergonomic Office Chair",
        variant_title: "Charcoal Black",
        sku: "CHR-BLK-01",
        hsn_code: "94013000",
        gst_rate_basis_points: 1800,
        quantity: 1,
        unit_original_price_paise: 100000,
        unit_selling_price_paise: 100000,
        unit_discount_paise: 10000,
        unit_discounted_price_paise: 90000,
        total_selling_price_paise: 90000,
        taxable_base_paise: 90000,
        cgst_paise: 8100,
        sgst_paise: 8100,
        igst_paise: 0,
        total_tax_paise: 16200,
        retailer_name: "Apex Furnishings",
        retailer_state: "Karnataka",
        created_at: "2026-11-17T15:00:00Z",
      },
    ],
    status_history: [
      {
        id: "hist-uuid-1",
        from_status: null,
        to_status: "PENDING_PAYMENT",
        reason: "ORDER_CREATED",
        created_at: "2026-11-17T15:00:00Z",
      },
    ],
    created_at: "2026-11-17T15:00:00Z",
    updated_at: "2026-11-17T15:00:00Z",
  };

  await t.test("createOrder() posts payload and passes Idempotency-Key header", async () => {
    let capturedUrl = "";
    let capturedOptions: RequestInit | undefined;

    globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      capturedUrl = input.toString();
      capturedOptions = init;
      return new Response(JSON.stringify(mockOrder), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await createOrder(
      {
        quote_id: "quo-uuid-789",
        reservation_id: "res-uuid-101",
        delivery_address_id: "addr-uuid-999",
      },
      "test-order-idem-key",
    );

    assert.equal(capturedUrl, "http://localhost:8000/api/v1/orders");
    assert.equal(capturedOptions?.method, "POST");
    assert.deepEqual(JSON.parse(capturedOptions?.body as string), {
      quote_id: "quo-uuid-789",
      reservation_id: "res-uuid-101",
      delivery_address_id: "addr-uuid-999",
    });

    const headers = capturedOptions?.headers as Record<string, string>;
    assert.equal(headers["Idempotency-Key"], "test-order-idem-key");
    assert.equal(res.id, "ord-uuid-123");
    assert.equal(res.order_number, "BSK-20261117-ABC123");
    assert.equal(res.status, "PENDING_PAYMENT");
    assert.equal(res.payment_status, "NOT_INITIATED");
    assert.equal(res.total_payable_paise, 111200);
    assert.equal(res.items.length, 1);
  });

  await t.test("orderApi.createOrder() invokes client method with inline address", async () => {
    let capturedOptions: RequestInit | undefined;

    globalThis.fetch = async (_input: RequestInfo | URL, init?: RequestInit) => {
      capturedOptions = init;
      return new Response(JSON.stringify(mockOrder), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await orderApi.createOrder({
      quote_id: "quo-uuid-789",
      reservation_id: "res-uuid-101",
      delivery_address: {
        full_name: "Rahul Verma",
        address_line1: "123 Indiranagar",
        city: "Bengaluru",
        state: "Karnataka",
        postal_code: "560038",
        phone: "+919876543210",
      },
    });

    assert.equal(res.order_number, "BSK-20261117-ABC123");
    const parsedBody = JSON.parse(capturedOptions?.body as string);
    assert.equal(parsedBody.delivery_address.city, "Bengaluru");
  });

  await t.test("getOrder() fetches order details by id", async () => {
    let capturedUrl = "";

    globalThis.fetch = async (input: RequestInfo | URL) => {
      capturedUrl = input.toString();
      return new Response(JSON.stringify(mockOrder), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await getOrder("ord-uuid-123");

    assert.equal(capturedUrl, "http://localhost:8000/api/v1/orders/ord-uuid-123");
    assert.equal(res.id, "ord-uuid-123");
    assert.equal(res.delivery_address.postal_code, "560038");
    assert.equal(res.status_history?.length, 1);
  });

  await t.test("listOrders() requests orders with query params", async () => {
    let capturedUrl = "";

    const mockListResponse: OrderListResponse = {
      orders: [mockOrder],
      total: 1,
    };

    globalThis.fetch = async (input: RequestInfo | URL) => {
      capturedUrl = input.toString();
      return new Response(JSON.stringify(mockListResponse), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await listOrders(10, 20);

    assert.equal(
      capturedUrl,
      "http://localhost:8000/api/v1/orders?limit=10&offset=20",
    );
    assert.equal(res.orders.length, 1);
    assert.equal(res.total, 1);
    assert.equal(res.orders[0].id, "ord-uuid-123");
  });

  await t.test("createOrder() raises ApiClientError on 409 conflict", async () => {
    globalThis.fetch = async () => {
      return new Response(
        JSON.stringify({
          error: {
            code: "QUOTE_ALREADY_ORDERED",
            message: "An order for this quote has already been created.",
          },
        }),
        {
          status: 409,
          headers: { "Content-Type": "application/json" },
        },
      );
    };

    await assert.rejects(
      async () => {
        await createOrder({
          quote_id: "quo-uuid-789",
          reservation_id: "res-uuid-101",
        });
      },
      (err: unknown) => {
        assert(err instanceof ApiClientError);
        assert.equal(err.status, 409);
        assert.equal(err.code, "QUOTE_ALREADY_ORDERED");
        return true;
      },
    );
  });
});
