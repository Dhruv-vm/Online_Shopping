import { apiClient } from "@/lib/api/client";

export type RecurringItem = { listing_id: string; quantity: number; product_name: string; variant_name: string | null; retailer_name: string; unit_price_paise_at_setup: number };
export type RecurringBasket = {
  id: string; name: string; status: "ACTIVE" | "PAUSED" | "CANCELLED" | "ENDED"; day_of_month: number;
  start_date: string; end_date: string | null; next_run_date: string | null; skip_dates: string[];
  delivery_address_id: string | null; items: RecurringItem[]; autopay: string;
  recent_runs: { scheduled_for: string; status: string; items_total_paise: number | null; changes: number; created_at: string }[];
  created_at: string;
};
export type CheckLine = {
  listing_id: string; product_name: string; retailer_name: string; quantity: number; status: string;
  previous_unit_price_paise: number; current_unit_price_paise: number | null; offer_unit_discount_paise: number;
  final_unit_price_paise: number | null; available_quantity: number; offers: string[]; line_total_paise: number; note: string | null;
};
export type PreOrderCheck = {
  checked_at: string; scheduled_for: string | null; lines: CheckLine[]; orderable_lines: number;
  items_total_paise: number; previous_total_paise: number; changes: string[]; delivery_address_set: boolean; note: string;
};

const base = "/api/v1/recurring-baskets";
export const listRecurring = () => apiClient.get<RecurringBasket[]>(base);
export const createRecurring = (body: { name: string; day_of_month: number; start_date: string; end_date?: string | null; delivery_address_id?: string | null }) =>
  apiClient.post<RecurringBasket>(base, body);
export const updateRecurring = (id: string, body: Record<string, unknown>) => apiClient.patch<RecurringBasket>(`${base}/${id}`, body);
export const recurringAction = (id: string, action: "pause" | "resume" | "skip" | "cancel") => apiClient.post<RecurringBasket>(`${base}/${id}/${action}`);
export const checkRecurring = (id: string) => apiClient.get<PreOrderCheck>(`${base}/${id}/check`);
export const loadRecurring = (id: string) => apiClient.post<{ loaded: number; skipped: string[]; message: string }>(`${base}/${id}/load-to-cart`);
