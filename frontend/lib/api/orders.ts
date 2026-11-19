import { apiClient } from "./client.ts";
import type {
  CreateOrderRequest,
  NotificationListResponse,
  Order,
  OrderCancellationResponse,
  OrderListResponse,
  OrderReturn,
  OrderTrackingResponse,
  ReturnCreateRequest,
} from "../../types/index.ts";

export async function createOrder(
  payload: CreateOrderRequest,
  idempotencyKey?: string,
): Promise<Order> {
  return apiClient.createOrder(payload, idempotencyKey);
}

export async function getOrder(orderId: string, accessToken?: string): Promise<Order> {
  return apiClient.getOrder(orderId, accessToken);
}

export async function guestLookupOrder(orderNumber: string, accessToken: string): Promise<Order> {
  return apiClient.guestLookupOrder(orderNumber, accessToken);
}

export async function listOrders(
  limit = 20,
  offset = 0,
  status?: string,
  search?: string,
  fromDate?: string,
  toDate?: string,
): Promise<OrderListResponse> {
  return apiClient.listOrders(limit, offset, status, search, fromDate, toDate);
}

export async function cancelOrder(
  orderId: string,
  reason: string,
  idempotencyKey?: string,
  accessToken?: string,
): Promise<OrderCancellationResponse> {
  return apiClient.cancelOrder(orderId, reason, idempotencyKey, accessToken);
}

export async function getOrderTracking(
  orderId: string,
  accessToken?: string,
): Promise<OrderTrackingResponse> {
  return apiClient.getOrderTracking(orderId, accessToken);
}

export async function requestReturn(
  orderId: string,
  payload: ReturnCreateRequest,
  idempotencyKey?: string,
  accessToken?: string,
): Promise<OrderReturn> {
  return apiClient.requestReturn(orderId, payload, idempotencyKey, accessToken);
}

export async function listOrderReturns(
  orderId: string,
  accessToken?: string,
): Promise<OrderReturn[]> {
  return apiClient.listOrderReturns(orderId, accessToken);
}

export async function listNotifications(
  limit = 50,
  offset = 0,
): Promise<NotificationListResponse> {
  return apiClient.listNotifications(limit, offset);
}

export async function getUnreadNotificationCount(): Promise<{ unread_count: number }> {
  return apiClient.getUnreadNotificationCount();
}

export async function markNotificationAsRead(
  notificationId: string,
): Promise<{ success: boolean }> {
  return apiClient.markNotificationAsRead(notificationId);
}

export const orderApi = {
  createOrder,
  getOrder,
  guestLookupOrder,
  listOrders,
  cancelOrder,
  getOrderTracking,
  requestReturn,
  listOrderReturns,
  listNotifications,
  getUnreadNotificationCount,
  markNotificationAsRead,
};
