/**
 * Stable Idempotency-Key for payment initiation (Version 2.0 Phase A2).
 *
 * One key is used for every "Pay" press on the same order while the checkout
 * page is open, so retries replay the same Razorpay order instead of creating
 * a new one. A key that belonged to a FAILED attempt is rejected by the API
 * with PAYMENT_ATTEMPT_FAILED; only then is a fresh key issued.
 */
export interface PaymentKeyState {
  orderId: string;
  key: string;
}

function randomPart(): string {
  const c = (globalThis as { crypto?: { randomUUID?: () => string } }).crypto;
  if (c && typeof c.randomUUID === "function") {
    return c.randomUUID();
  }
  // randomUUID is unavailable outside secure contexts (plain-http LAN hosts).
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

export function makePaymentKey(orderId: string): string {
  return `pay-${orderId}-${randomPart()}`.slice(0, 128);
}

/** Keep the current key for the same order; issue a new one for a different order. */
export function keyForOrder(
  state: PaymentKeyState | null,
  orderId: string,
): PaymentKeyState {
  if (state && state.orderId === orderId) {
    return state;
  }
  return { orderId, key: makePaymentKey(orderId) };
}

/** True when the API refused the key because its attempt permanently failed. */
export function shouldRotatePaymentKey(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    (error as { code?: unknown }).code === "PAYMENT_ATTEMPT_FAILED"
  );
}
