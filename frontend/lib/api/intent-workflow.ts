import { apiClient } from "@/lib/api/client";

export type IntentItemIn = { name: string; quantity: number; specs?: string | null };
export type IntentSubmit = {
  title: string;
  items: IntentItemIn[];
  budget_paise?: number | null;
  frequency: string;
  pincode?: string | null;
  purchase_by?: string | null;
  notes?: string | null;
};
export type IntentMatch = {
  listing_id: string; product_name: string; product_slug: string; variant_name: string; retailer_name: string;
  price_paise: number; original_price_paise: number; available_quantity: number; offers: string[];
};
export type IntentItemResult = {
  name: string; quantity: number; specs: string | null; understood_as: string; category: string | null;
  status: "AVAILABLE" | "NOT_AVAILABLE"; matches: IntentMatch[]; retailer_count: number; next_step: string;
  demand: null | {
    pool_id: string; display_name: string; unique_customers: number; visibility_threshold: number;
    visible_to_retailers: boolean; status: string; signal_recorded_now: boolean;
  };
};
export type IntentWorkflow = {
  intention: { id: string; title: string; frequency: string; budget_paise: number | null; notes: string | null; is_active: boolean };
  items_requested: IntentItemIn[]; pincode: string | null; purchase_by: string | null; updated_existing: boolean;
  status: "MATCHED" | "PARTIALLY_MATCHED" | "WAITING_FOR_SUPPLY"; items: IntentItemResult[];
  cheapest_total_paise: number; within_budget: boolean | null; can_create_basket: boolean; next_steps: string[]; analyzed_at: string;
};
export type IntentSummary = {
  id: string; title: string; frequency: string; budget_paise: number | null; pincode: string | null;
  item_count: number; is_active: boolean; last_status: string | null; analyzed_at: string | null;
};

export const submitIntent = (body: IntentSubmit) => apiClient.post<IntentWorkflow>("/api/v1/intent/workflow", body);
export const updateIntent = (id: string, body: IntentSubmit) => apiClient.put<IntentWorkflow>(`/api/v1/intent/workflow/${id}`, body);
export const getIntent = (id: string) => apiClient.get<IntentWorkflow>(`/api/v1/intent/workflow/${id}`);
export const listIntents = () => apiClient.get<IntentSummary[]>("/api/v1/intent/workflow");
export const createIntentBasket = (id: string) =>
  apiClient.post<{ added: { item: string; product_name: string; retailer_name: string; quantity: number }[]; skipped: string[]; message: string }>(
    `/api/v1/intent/workflow/${id}/basket`,
  );
