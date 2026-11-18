import test from "node:test";
import assert from "node:assert/strict";
import { ApiClientError } from "./client.ts";
import {
  initiatePayment,
  verifyPayment,
  requestRefund,
  paymentApi,
} from "./payments.ts";
import type {
  PaymentInitiateResponse,
  PaymentVerifyResponse,
  PaymentRefundResponse,
} from "../../types/index.ts";

test("Payments API Client integration", async (t) => {
  const originalFetch = globalThis.fetch;

  t.afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  const mockInitiateResponse: PaymentInitiateResponse = {
    payment_id: "pay-uuid-001",
    order_id: "ord-uuid-123",
    provider_order_id: "order_rzp_123456",
    amount_paise: 111200,
    currency: "INR",
    razorpay_key_id: "rzp_test_placeholder_key",
    attempt_status: "PENDING",
    notes: { order_number: "BSK-20261117-ABC123" },
    created_at: "2026-11-18T10:00:00Z",
  };

  const mockVerifyResponse: PaymentVerifyResponse = {
    payment_id: "pay-uuid-001",
    order_id: "ord-uuid-123",
    status: "CAPTURED",
    order_status: "CONFIRMED",
    amount_paise: 111200,
    currency: "INR",
    message: "Payment verified and order confirmed successfully",
  };

  const mockRefundResponse: PaymentRefundResponse = {
    refund_id: "ref-uuid-001",
    payment_id: "pay-uuid-001",
    order_id: "ord-uuid-123",
    provider_refund_id: "rfnd_rzp_987654",
    amount_paise: 50000,
    currency: "INR",
    status: "PROCESSED",
    reason: "Customer requested partial cancellation",
    created_at: "2026-11-18T10:30:00Z",
  };

  await t.test(
    "initiatePayment() posts to /api/v1/orders/{id}/payments and passes Idempotency-Key",
    async () => {
      let capturedUrl = "";
      let capturedOptions: RequestInit | undefined;

      globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
        capturedUrl = input.toString();
        capturedOptions = init;
        return new Response(JSON.stringify(mockInitiateResponse), {
          status: 201,
          headers: { "Content-Type": "application/json" },
        });
      };

      const res = await initiatePayment("ord-uuid-123", "idemp-pay-key-1");

      assert.equal(capturedUrl, "http://localhost:8000/api/v1/orders/ord-uuid-123/payments");
      assert.equal(capturedOptions?.method, "POST");
      const headers = capturedOptions?.headers as Record<string, string>;
      assert.equal(headers["Idempotency-Key"], "idemp-pay-key-1");
      assert.equal(res.provider_order_id, "order_rzp_123456");
      assert.equal(res.amount_paise, 111200);
      assert.equal(res.attempt_status, "PENDING");
    },
  );

  await t.test(
    "verifyPayment() posts signature verification payload to /payments/verify",
    async () => {
      let capturedUrl = "";
      let capturedOptions: RequestInit | undefined;

      globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
        capturedUrl = input.toString();
        capturedOptions = init;
        return new Response(JSON.stringify(mockVerifyResponse), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      };

      const res = await verifyPayment("ord-uuid-123", {
        razorpay_order_id: "order_rzp_123456",
        razorpay_payment_id: "pay_rzp_789012",
        razorpay_signature: "valid_hmac_sha256_signature",
      });

      assert.equal(
        capturedUrl,
        "http://localhost:8000/api/v1/orders/ord-uuid-123/payments/verify",
      );
      assert.equal(capturedOptions?.method, "POST");
      const body = JSON.parse(capturedOptions?.body as string);
      assert.equal(body.razorpay_order_id, "order_rzp_123456");
      assert.equal(body.razorpay_payment_id, "pay_rzp_789012");
      assert.equal(body.razorpay_signature, "valid_hmac_sha256_signature");

      assert.equal(res.status, "CAPTURED");
      assert.equal(res.order_status, "CONFIRMED");
    },
  );

  await t.test(
    "verifyPayment() raises ApiClientError on 400 signature mismatch",
    async () => {
      globalThis.fetch = async () => {
        return new Response(
          JSON.stringify({
            error: {
              code: "SIGNATURE_VERIFICATION_FAILED",
              message: "Invalid Razorpay payment signature",
              request_id: "req-err-400",
              details: [],
            },
          }),
          {
            status: 400,
            headers: { "Content-Type": "application/json" },
          },
        );
      };

      await assert.rejects(
        async () => {
          await verifyPayment("ord-uuid-123", {
            razorpay_order_id: "order_rzp_123456",
            razorpay_payment_id: "pay_rzp_tampered",
            razorpay_signature: "invalid_sig",
          });
        },
        (err: unknown) => {
          assert(err instanceof ApiClientError);
          assert.equal(err.status, 400);
          assert.equal(err.code, "SIGNATURE_VERIFICATION_FAILED");
          assert.equal(err.message, "Invalid Razorpay payment signature");
          return true;
        },
      );
    },
  );

  await t.test(
    "requestRefund() posts refund request and supports idempotency key",
    async () => {
      let capturedUrl = "";
      let capturedOptions: RequestInit | undefined;

      globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
        capturedUrl = input.toString();
        capturedOptions = init;
        return new Response(JSON.stringify(mockRefundResponse), {
          status: 201,
          headers: { "Content-Type": "application/json" },
        });
      };

      const res = await requestRefund(
        "ord-uuid-123",
        {
          amount_paise: 50000,
          reason: "Customer requested partial cancellation",
        },
        "idemp-rfnd-key-1",
      );

      assert.equal(capturedUrl, "http://localhost:8000/api/v1/orders/ord-uuid-123/refunds");
      assert.equal(capturedOptions?.method, "POST");
      const headers = capturedOptions?.headers as Record<string, string>;
      assert.equal(headers["Idempotency-Key"], "idemp-rfnd-key-1");
      const body = JSON.parse(capturedOptions?.body as string);
      assert.equal(body.amount_paise, 50000);
      assert.equal(res.status, "PROCESSED");
      assert.equal(res.amount_paise, 50000);
    },
  );

  await t.test(
    "requestRefund() raises ApiClientError on 409 REFUND_EXCEEDS_CAPTURED_AMOUNT",
    async () => {
      globalThis.fetch = async () => {
        return new Response(
          JSON.stringify({
            error: {
              code: "REFUND_EXCEEDS_CAPTURED_AMOUNT",
              message: "Refund amount exceeds refundable balance",
              request_id: "req-err-409",
              details: [],
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
          await requestRefund("ord-uuid-123", {
            amount_paise: 200000,
          });
        },
        (err: unknown) => {
          assert(err instanceof ApiClientError);
          assert.equal(err.status, 409);
          assert.equal(err.code, "REFUND_EXCEEDS_CAPTURED_AMOUNT");
          return true;
        },
      );
    },
  );

  await t.test("paymentApi export delegates correctly", async () => {
    globalThis.fetch = async () => {
      return new Response(JSON.stringify(mockInitiateResponse), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await paymentApi.initiatePayment("ord-uuid-123");
    assert.equal(res.payment_id, "pay-uuid-001");
  });
});
