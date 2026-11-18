import { apiClient } from "./client.ts";
import type {
  PaymentInitiateResponse,
  PaymentVerifyRequest,
  PaymentVerifyResponse,
  PaymentRefundRequest,
  PaymentRefundResponse,
} from "../../types/index.ts";

export async function initiatePayment(
  orderId: string,
  idempotencyKey?: string,
): Promise<PaymentInitiateResponse> {
  return apiClient.initiatePayment(orderId, idempotencyKey);
}

export async function verifyPayment(
  orderId: string,
  payload: PaymentVerifyRequest,
): Promise<PaymentVerifyResponse> {
  return apiClient.verifyPayment(orderId, payload);
}

export async function requestRefund(
  orderId: string,
  payload: PaymentRefundRequest,
  idempotencyKey?: string,
): Promise<PaymentRefundResponse> {
  return apiClient.requestRefund(orderId, payload, idempotencyKey);
}

export const paymentApi = {
  initiatePayment,
  verifyPayment,
  requestRefund,
};
