import { apiClient } from "./client.ts";
import type { CreateOrderRequest, Order, OrderListResponse } from "../../types/index.ts";

export async function createOrder(
  payload: CreateOrderRequest,
  idempotencyKey?: string,
): Promise<Order> {
  return apiClient.createOrder(payload, idempotencyKey);
}

export async function getOrder(orderId: string): Promise<Order> {
  return apiClient.getOrder(orderId);
}

export async function listOrders(
  limit = 20,
  offset = 0,
): Promise<OrderListResponse> {
  return apiClient.listOrders(limit, offset);
}

export const orderApi = {
  createOrder,
  getOrder,
  listOrders,
};
