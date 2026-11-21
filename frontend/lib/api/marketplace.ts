/**
 * Marketplace-completion API client (typed). Amounts are integer paise.
 * Covers: deal assistant, price comparison & alerts, retailer price insights,
 * customer-started group buys, retailer onboarding & media, admin governance.
 */
import { apiClient } from "./client.ts";
import type { Auction, ExchangeRequest, GroupBuyCampaign } from "./phase3.ts";

type UUID = string;
const q = (params: Record<string, string | number | boolean | undefined | null>) => {
  const s = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") s.set(k, String(v));
  const out = s.toString();
  return out ? `?${out}` : "";
};

// ------------------------------------------------------------ Deal assistant
export interface AssistantSeller {
  listing_id: UUID; retailer_id: UUID | null; retailer_name: string;
  price_paise: number; mrp_paise: number; available_quantity: number; negotiable: boolean;
}
export interface AssistantOption {
  product_id: UUID; name: string; brand: string; category_slug: string; image_url: string | null;
  best_price_paise: number; sellers: AssistantSeller[]; within_budget: boolean; explanation: string;
}
export interface AssistantReply {
  mode: "rule_based"; ai_provider_configured: boolean; understood: Record<string, unknown>;
  message: string; options: AssistantOption[]; alternatives: AssistantOption[]; disclaimer: string;
}
export const askAssistant = (message: string) => apiClient.post<AssistantReply>("/api/v1/assistant/chat", { message });

// ------------------------------------------------------------ Price intelligence (3F)
export interface PriceComparisonOffer {
  listing_id: UUID; retailer_id: UUID; retailer_name: string; retailer_state: string | null;
  selling_price_paise: number; mrp_paise: number; discount_from_mrp_pct: number;
  available_quantity: number; in_stock: boolean; is_cheapest: boolean; difference_from_cheapest_paise: number;
}
export interface PriceComparison {
  variant_id: UUID; product_name: string; variant_name: string; offers: PriceComparisonOffer[];
  cheapest_price_paise: number | null; price_spread_paise: number; explanation: string;
}
export const comparePrices = (variantId: UUID) =>
  apiClient.get<PriceComparison>(`/api/v1/price-intelligence/variants/${encodeURIComponent(variantId)}/compare`);

export interface PriceAlert {
  id: UUID; variant_id: UUID; product_name: string; variant_name: string; target_price_paise: number;
  current_best_price_paise: number | null; status: "ACTIVE" | "TRIGGERED" | "CANCELLED";
  triggered_price_paise: number | null; triggered_at: string | null; created_at: string;
}
export const listPriceAlerts = () => apiClient.get<PriceAlert[]>("/api/v1/price-intelligence/alerts");
export const createPriceAlert = (variant_id: UUID, target_price_paise: number) =>
  apiClient.post<PriceAlert>("/api/v1/price-intelligence/alerts", { variant_id, target_price_paise });
export const cancelPriceAlert = (id: UUID) => apiClient.delete<PriceAlert>(`/api/v1/price-intelligence/alerts/${encodeURIComponent(id)}`);

export interface RetailerPriceInsight {
  listing_id: UUID; product_name: string; variant_name: string; my_price_paise: number;
  competitor_count: number; lowest_competitor_price_paise: number | null; my_rank: number;
  gap_to_lowest_paise: number | null; days_of_history: number; active_price_alerts: number;
}
export const getRetailerPriceInsights = () => apiClient.get<RetailerPriceInsight[]>("/api/v1/retailer/price-insights");

export interface PriceDataQuality {
  active_listings: number; listings_without_history: number; listings_with_demo_history: number;
  live_ticks: number; demo_ticks: number; stale_listings_7d: number; selling_above_mrp: number;
  large_daily_swings: number; active_price_alerts: number; generated_at: string;
}
export const getPriceDataQuality = () => apiClient.get<PriceDataQuality>("/api/v1/admin/price-intelligence/quality");

// ------------------------------------------------------------ Group buys (3B)
export interface GroupBuyTemplate {
  id: UUID; listing_id: UUID; retailer_id: UUID; retailer_name: string; product_name: string;
  image_url: string | null; min_participants: number; max_participants: number; discount_percent: number;
  duration_hours: number; max_quantity_per_member: number; max_open_campaigns: number; open_campaigns: number;
  list_price_paise: number; group_price_paise: number; is_active: boolean;
}
export const listGroupBuyTemplates = () =>
  apiClient.get<{ items: GroupBuyTemplate[]; total: number }>("/api/v1/community-buying/templates");
export const startGroupBuy = (template_id: UUID, quantity = 1) =>
  apiClient.post<Record<string, unknown> & { id: UUID }>("/api/v1/community-buying/start", { template_id, quantity });
export const listMyGroupBuyTemplates = () =>
  apiClient.get<{ items: GroupBuyTemplate[]; total: number }>("/api/v1/retailer/community-buying/templates");
export const upsertGroupBuyTemplate = (body: {
  listing_id: UUID; min_participants: number; max_participants: number; discount_percent: number;
  duration_hours: number; max_quantity_per_member: number; max_open_campaigns: number;
}) => apiClient.post<GroupBuyTemplate>("/api/v1/retailer/community-buying/templates", body);
export const deactivateGroupBuyTemplate = (id: UUID) =>
  apiClient.post<GroupBuyTemplate>(`/api/v1/retailer/community-buying/templates/${encodeURIComponent(id)}/deactivate`, {});

// ------------------------------------------------------------ Retailer onboarding & media
export type DocumentType = "GSTIN_CERTIFICATE" | "PAN" | "TRADE_LICENSE" | "ADDRESS_PROOF" | "FSSAI" | "OTHER";
export interface RetailerDocument {
  id: UUID; document_type: DocumentType; document_number: string | null; has_file: boolean;
  status: "PENDING" | "VERIFIED" | "REJECTED"; rejection_reason: string | null; created_at: string;
}
export const listRetailerDocuments = () => apiClient.get<RetailerDocument[]>("/api/v1/retailer/documents");
export const submitRetailerDocument = (body: {
  document_type: DocumentType; document_number?: string;
  content_base64?: string; content_type?: "image/jpeg" | "image/png" | "image/webp" | "application/pdf";
}) => apiClient.post<RetailerDocument>("/api/v1/retailer/documents", body);
export const resubmitVerification = () => apiClient.post<Record<string, unknown>>("/api/v1/retailer/verification/resubmit", {});
export const uploadListingImage = (listingId: UUID, content_base64: string, content_type: "image/jpeg" | "image/png" | "image/webp") =>
  apiClient.put<{ listing_id: UUID; image_url: string | null }>(`/api/v1/retailer/listings/${encodeURIComponent(listingId)}/image`, { content_base64, content_type });
export const removeListingImage = (listingId: UUID) =>
  apiClient.delete<{ listing_id: UUID; image_url: null }>(`/api/v1/retailer/listings/${encodeURIComponent(listingId)}/image`);
export const uploadProductImage = (productId: UUID, content_base64: string, content_type: string, make_primary = false) =>
  apiClient.post<{ id: UUID; url: string; is_primary: boolean }>(`/api/v1/admin/catalogue/products/${encodeURIComponent(productId)}/images`, { content_base64, content_type, make_primary });

export const deleteProductImage = (imageId: UUID) =>
  apiClient.delete<void>(`/api/v1/admin/catalogue/images/${encodeURIComponent(imageId)}`);

/** Read a File as base64 (without the data: prefix). */
export function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result).split(",", 2)[1] ?? "");
    r.onerror = () => reject(r.error);
    r.readAsDataURL(file);
  });
}

// ------------------------------------------------------------ Admin governance
export interface AdminUser {
  id: UUID; email: string; full_name: string; role: string; is_active: boolean;
  preferred_language: string | null; is_test_fixture: boolean; created_at: string;
}
export const adminListUsers = (p: { q?: string; role?: string; is_active?: boolean; include_test_fixtures?: boolean; limit?: number; offset?: number } = {}) =>
  apiClient.get<{ items: AdminUser[]; total: number }>(`/api/v1/admin/users${q(p)}`);
export const adminSetUserStatus = (id: UUID, is_active: boolean, reason: string) =>
  apiClient.post<AdminUser>(`/api/v1/admin/users/${encodeURIComponent(id)}/status`, { is_active, reason });

export interface AdminOrder {
  id: UUID; order_number: string; customer_email: string | null; status: string; payment_status: string;
  total_payable_paise: number; item_count: number; retailer_count: number; created_at: string;
}
export const adminListOrders = (p: { status?: string; payment_status?: string; q?: string; include_test_fixtures?: boolean; limit?: number; offset?: number } = {}) =>
  apiClient.get<{ items: AdminOrder[]; total: number }>(`/api/v1/admin/orders${q(p)}`);

export interface AuditEntry {
  id: UUID; actor_email: string | null; method: string; route: string; path: string;
  entity_id: string | null; status_code: number; created_at: string;
  /** Structured context, e.g. { action: "suspend", reason: "…" }. */
  details?: Record<string, unknown>;
}
export const adminAuditLogs = (p: { actor?: string; entity_id?: string; limit?: number; offset?: number } = {}) =>
  apiClient.get<{ items: AuditEntry[]; total: number }>(`/api/v1/admin/audit-logs${q(p)}`);

export interface SystemHealth {
  components: { name: string; status: "ok" | "degraded" | "down" | "not_configured"; detail: string }[];
  outbox_pending: number; outbox_failed: number; oldest_pending_event_seconds: number | null;
  background_jobs: Record<string, { last_run_at: string; last_ok: boolean; interval_seconds: number; last_error: string | null }>;
  quarantined_test_records: number; checked_at: string;
}
export const adminSystemHealth = () => apiClient.get<SystemHealth>("/api/v1/admin/system/health");
export const adminModerateRfq = (id: UUID, reason: string) =>
  apiClient.post<Record<string, unknown>>(`/api/v1/admin/exchange/requests/${encodeURIComponent(id)}/cancel`, { reason });

// ------------------------------------------------------------ Vision status (3I)
export const getVisionStatus = () =>
  apiClient.get<{ ocr_available: boolean; provider: string; manual_fallback: boolean; message: string }>("/api/v1/vision/status");

// ------------------------------------------------------------ Admin marketplace monitoring
export const adminListRfqs = (p: { status?: string; limit?: number; offset?: number } = {}) =>
  apiClient.get<{ items: ExchangeRequest[]; total: number }>(`/api/v1/admin/exchange/requests${q(p)}`);
export const adminListCampaigns = (p: { status?: string; limit?: number; offset?: number } = {}) =>
  apiClient.get<{ items: GroupBuyCampaign[]; total: number }>(`/api/v1/admin/community-buying/campaigns${q(p)}`);
export const adminCancelCampaign = (id: UUID) =>
  apiClient.post<GroupBuyCampaign>(`/api/v1/admin/community-buying/campaigns/${encodeURIComponent(id)}/cancel`, {});
export const adminListAuctions = (p: { status?: string; limit?: number; offset?: number } = {}) =>
  apiClient.get<{ items: Auction[]; total: number }>(`/api/v1/admin/auctions${q(p)}`);
