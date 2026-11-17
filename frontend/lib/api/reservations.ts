import { apiClient } from "./client.ts";
import type {
  Reservation,
  ReservationCreatePayload,
  ReservationReleaseResponse,
} from "../../types";

export const reservationApi = {
  /**
   * Atomically reserve inventory from an active checkout quote.
   */
  async createReservation(
    payload: ReservationCreatePayload,
    idempotencyKey?: string,
  ): Promise<Reservation> {
    const headers: Record<string, string> = {};
    if (idempotencyKey) {
      headers["Idempotency-Key"] = idempotencyKey;
    }
    return apiClient.post<Reservation>(
      "/api/v1/reservations",
      payload,
      { headers },
    );
  },

  /**
   * Retrieve reservation details, status, and remaining hold seconds.
   */
  async getReservation(id: string): Promise<Reservation> {
    return apiClient.get<Reservation>(`/api/v1/reservations/${id}`);
  },

  /**
   * Explicitly release an active reservation, returning stock to available inventory.
   */
  async releaseReservation(id: string): Promise<ReservationReleaseResponse> {
    return apiClient.post<ReservationReleaseResponse>(
      `/api/v1/reservations/${id}/release`,
      {},
    );
  },
};
