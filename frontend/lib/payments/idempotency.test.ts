import assert from "node:assert/strict";
import { test } from "node:test";
import { ApiClientError } from "../api/client.ts";
import {
  keyForOrder,
  makePaymentKey,
  shouldRotatePaymentKey,
} from "./idempotency.ts";

test("the same order keeps one key across retries", () => {
  const first = keyForOrder(null, "ord-1");
  const retry = keyForOrder(first, "ord-1");
  assert.equal(retry, first);
  assert.equal(retry.key, first.key);
});

test("a different order gets a different key", () => {
  const a = keyForOrder(null, "ord-1");
  const b = keyForOrder(a, "ord-2");
  assert.equal(b.orderId, "ord-2");
  assert.notEqual(b.key, a.key);
});

test("keys are unique and fit the 128-character column", () => {
  const k1 = makePaymentKey("8b0c7c52-1f6f-4c39-9d0b-6c1a1c7f2a10");
  const k2 = makePaymentKey("8b0c7c52-1f6f-4c39-9d0b-6c1a1c7f2a10");
  assert.notEqual(k1, k2);
  assert.ok(k1.length <= 128);
  assert.ok(k1.startsWith("pay-8b0c7c52"));
});

test("only a failed-attempt error rotates the key", () => {
  assert.equal(
    shouldRotatePaymentKey(
      new ApiClientError("failed", 409, "PAYMENT_ATTEMPT_FAILED"),
    ),
    true,
  );
  assert.equal(
    shouldRotatePaymentKey(new ApiClientError("x", 409, "ORDER_NOT_PAYABLE")),
    false,
  );
  assert.equal(shouldRotatePaymentKey(new Error("network")), false);
  assert.equal(shouldRotatePaymentKey(null), false);
});
