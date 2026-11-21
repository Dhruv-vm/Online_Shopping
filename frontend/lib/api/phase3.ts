/**
 * Phase 3 marketplace API client (typed). All amounts are integer paise.
 * Errors surface as ApiClientError { code, status, message, details } — see
 * FRONTEND_INTEGRATION_GUIDE.md for per-endpoint error codes.
 */
import { apiClient } from "./client.ts";

type UUID = string;
const q = (params: Record<string, string | number | boolean | undefined | null>) => {
  const s = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") s.set(k, String(v));
  const out = s.toString();
  return out ? `?${out}` : "";
};

// ---------------------------------------------------------------- 3F Price Intelligence
export type PriceBadge = "GENUINE_DISCOUNT" | "MRP_INFLATED" | "NO_SPECIAL_DISCOUNT" | "INSUFFICIENT_HISTORY";
export interface PricePoint { date: string; price_paise: number; day_low_paise: number; mrp_paise: number; source?: "LIVE" | "DEMO_SEED" }
export interface PriceIntelligence {
  listing_id: UUID; currency: string; window_days: number;
  current_price_paise: number; current_mrp_paise: number;
  lowest_price_paise: number; highest_price_paise: number;
  average_price_30d_paise: number | null; average_price_90d_paise: number | null;
  current_vs_30d_average_pct: number | null; discount_from_mrp_pct: number;
  is_lowest_in_window: boolean; days_of_history: number;
  badge: PriceBadge; badge_reason: string; history: PricePoint[];
  /** True when part of the history is demonstration data from the demo seed. */
  contains_demo_data?: boolean; demo_days?: number; demo_data_notice?: string | null;
}
export const getPriceIntelligence = (listingId: UUID, days = 90) =>
  apiClient.get<PriceIntelligence>(`/api/v1/price-intelligence/listings/${encodeURIComponent(listingId)}${q({ days })}`);

// ---------------------------------------------------------------- 3G Sale Stream
export type SaleStreamEventType = "PRICE_DROP" | "FLASH_DEAL" | "HOT_SELLER";
export interface SaleStreamItem {
  id: UUID; event_type: SaleStreamEventType; listing_id: UUID; product_id: UUID;
  product_name: string; variant_name: string; image_url: string | null;
  retailer_id: UUID; retailer_name: string; category_slug: string | null;
  old_price_paise: number; deal_price_paise: number; current_price_paise: number;
  discount_pct: number; stock_remaining: number; units_sold_24h: number | null;
  starts_at: string; expires_at: string; seconds_remaining: number; created_at: string;
}
export interface SaleStreamResponse { items: SaleStreamItem[]; next_cursor: string | null; server_time: string; poll_after_seconds: number }
export const getSaleStream = (p: { event_type?: SaleStreamEventType; category_slug?: string; before?: string; since?: string; limit?: number } = {}) =>
  apiClient.get<SaleStreamResponse>(`/api/v1/sale-stream/live${q(p)}`);

// ---------------------------------------------------------------- 3H Bharat Multilingual
export interface LanguageItem { code: string; name: string; native_name: string; script: string }
export const listLanguages = () => apiClient.get<{ default: string; languages: LanguageItem[] }>("/api/v1/i18n/languages");
export const getLanguagePreference = () => apiClient.get<{ language: string }>("/api/v1/i18n/preference");
export const setLanguagePreference = (language: string) => apiClient.put<{ language: string }>("/api/v1/i18n/preference", { language });
export const getTranslations = (entityType: "product" | "category" | "offer", ids: UUID[], lang: string) =>
  apiClient.get<{ entity_type: string; language: string; translations: Record<UUID, { name?: string; description?: string }> }>(
    `/api/v1/i18n/translations${q({ entity_type: entityType, lang, ids: ids.join(",") })}`,
  );
export const upsertTranslation = (body: { entity_type: "product" | "category" | "offer"; entity_id: UUID; language: string; fields: { name?: string; description?: string } }) =>
  apiClient.put<void>("/api/v1/admin/i18n/translations", body);

// ---------------------------------------------------------------- 3A Demand Gap
export interface DemandOffer { retailer_id: UUID; retailer_name: string; listing_id: UUID; offered_price_paise: number; note: string | null; created_at: string }
export interface DemandPool {
  id: UUID; display_name: string; normalized_product_name: string; category_id: UUID | null; pincode: string | null;
  total_demand_count: number; unique_users_count: number; visibility_threshold: number;
  status: "OPEN" | "FULFILLED" | "EXPIRED"; last_signal_at: string; fulfilled_at: string | null; created_at: string;
  offers: DemandOffer[]; responded_by_me: boolean | null;
}
export interface DemandPoolList { items: DemandPool[]; total: number }
export const logDemandSignal = (body: { query_text?: string; listing_id?: UUID; category_id?: UUID; pincode?: string; signal_type?: "OUT_OF_STOCK" | "WISHLIST" }) =>
  apiClient.post<{ pool: DemandPool; deduplicated: boolean }>("/api/v1/demand/signal", body);
export const joinDemandPool = (poolId: UUID, pincode?: string) =>
  apiClient.post<{ pool: DemandPool; deduplicated: boolean }>(`/api/v1/demand/pools/${poolId}/join`, { pincode });
export const browseDemandPools = (p: { q?: string; pincode?: string; limit?: number; offset?: number } = {}) =>
  apiClient.get<DemandPoolList>(`/api/v1/demand/pools${q(p)}`);
export const myDemandRequests = () => apiClient.get<DemandPoolList>("/api/v1/demand/my-requests");
export const retailerDemandGaps = (p: { pincode?: string; category_id?: UUID; limit?: number; offset?: number } = {}) =>
  apiClient.get<DemandPoolList>(`/api/v1/retailer/demand-gaps${q(p)}`);
export const retailerFulfillDemand = (poolId: UUID, listingId: UUID, note?: string) =>
  apiClient.post<DemandPool>(`/api/v1/retailer/demand-gaps/${poolId}/fulfill`, { listing_id: listingId, note });
export const adminDemandPools = (p: { status?: string; limit?: number; offset?: number } = {}) =>
  apiClient.get<DemandPoolList>(`/api/v1/admin/demand/pools${q(p)}`);
export const adminUpdateDemandPool = (poolId: UUID, body: { status?: string; visibility_threshold?: number }) =>
  apiClient.patch<DemandPool>(`/api/v1/admin/demand/pools/${poolId}`, body);
export const adminDemandTrends = (days = 30) =>
  apiClient.get<{ daily: { date: string; signals: number }[]; top_pools: DemandPool[] }>(`/api/v1/admin/demand/trends${q({ days })}`);

// ---------------------------------------------------------------- 3B Community Buying
export interface GroupBuyCampaign {
  id: UUID; listing_id: UUID; retailer_id: UUID; retailer_name: string; product_name: string; image_url: string | null;
  title: string; min_participants: number; max_participants: number; current_participants: number;
  participants_needed: number; total_quantity: number; max_quantity_per_member: number; discount_percent: number;
  list_price_paise: number; group_price_paise: number; status: "OPEN" | "SUCCESSFUL" | "FAILED" | "CANCELLED";
  expires_at: string; seconds_remaining: number;
  /** True when a customer started this group on retailer-published terms. */
  started_by_customer?: boolean;
  /** First initial of each real member (no names or contacts). */
  participant_initials?: string[];
  my_membership: { status: string; quantity: number; order_id: string | null } | null;
}
export interface CampaignCreate { listing_id: UUID; title?: string; min_participants: number; max_participants: number; discount_percent: number; duration_hours: number; max_quantity_per_member?: number }
export const listCampaigns = (p: { limit?: number; offset?: number } = {}) =>
  apiClient.get<{ items: GroupBuyCampaign[]; total: number }>(`/api/v1/community-buying/campaigns${q(p)}`);
export const getCampaign = (id: UUID) => apiClient.get<GroupBuyCampaign>(`/api/v1/community-buying/campaigns/${id}`);
export const joinCampaign = (id: UUID, quantity = 1) => apiClient.post<GroupBuyCampaign>(`/api/v1/community-buying/campaigns/${id}/join`, { quantity });
export const leaveCampaign = (id: UUID) => apiClient.post<GroupBuyCampaign>(`/api/v1/community-buying/campaigns/${id}/leave`);
export type CampaignInvite = { token: string; url: string; expires_at: string; message: string; whatsapp_url: string; sms_url: string };
/** Creates a secure, expiring invitation (campaign facts only, nothing about the sender). */
export const shareCampaign = (id: UUID) => apiClient.post<CampaignInvite>(`/api/v1/community-buying/campaigns/${id}/invites`);
export type InvitePreview = {
  campaign_id: UUID; title: string; product_name: string; list_price_paise: number; group_price_paise: number; discount_bps: number;
  current_participants: number; min_participants: number; max_participants: number;
  campaign_expires_at: string; invite_expires_at: string; can_join: boolean; reason: string | null;
};
export const previewInvite = (token: string) => apiClient.get<InvitePreview>(`/api/v1/community-buying/invites/${encodeURIComponent(token)}`);
export const joinViaInvite = (token: string, quantity = 1) =>
  apiClient.post<GroupBuyCampaign>(`/api/v1/community-buying/invites/${encodeURIComponent(token)}/join`, { quantity });
export const retailerCampaigns = (status?: string) =>
  apiClient.get<{ items: GroupBuyCampaign[]; total: number }>(`/api/v1/retailer/community-buying/campaigns${q({ status })}`);
export const retailerCreateCampaign = (body: CampaignCreate) => apiClient.post<GroupBuyCampaign>("/api/v1/retailer/community-buying/campaigns", body);
export const retailerCancelCampaign = (id: UUID) => apiClient.post<GroupBuyCampaign>(`/api/v1/retailer/community-buying/campaigns/${id}/cancel`);

// ---------------------------------------------------------------- 3C Community Exchange (RFQ)
export interface ManifestItem { name: string; quantity: number; unit?: string | null; notes?: string | null }
export interface ExchangeBidLine { manifest_index: number; item_name: string; listing_id: UUID; product_name: string; quantity: number; unit_price_paise: number; list_price_paise: number; line_total_paise: number }
export interface ExchangeBid {
  id: UUID; retailer_id: UUID; retailer_name: string; retailer_rating: number; bid_amount_paise: number;
  estimated_delivery_hours: number; items_covered: number; items_requested: number; notes: string | null;
  status: "SUBMITTED" | "ACCEPTED" | "REJECTED" | "WITHDRAWN"; lines: ExchangeBidLine[]; created_at: string; updated_at: string;
}
export interface ExchangeRequest {
  id: UUID; title: string; delivery_pincode: string; budget_limit_paise: number | null; items: ManifestItem[];
  status: "BIDDING_OPEN" | "AWARDED" | "EXPIRED" | "CANCELLED"; accepted_bid_id: UUID | null;
  expires_at: string; created_at: string; bid_count: number; bids: ExchangeBid[] | null; my_bid: ExchangeBid | null;
}
export const createRfq = (body: { title: string; delivery_pincode: string; budget_limit_paise?: number; items: ManifestItem[]; bidding_hours?: number }) =>
  apiClient.post<ExchangeRequest>("/api/v1/exchange/requests", body);
export const myRfqs = () => apiClient.get<{ items: ExchangeRequest[]; total: number }>("/api/v1/exchange/requests");
export const getRfq = (id: UUID) => apiClient.get<ExchangeRequest>(`/api/v1/exchange/requests/${id}`);
export const acceptRfqBid = (id: UUID, bidId: UUID) =>
  apiClient.post<{ request: ExchangeRequest; cart_id: UUID; awarded_lines: number; message: string }>(`/api/v1/exchange/requests/${id}/accept-bid`, { bid_id: bidId });
export const cancelRfq = (id: UUID) => apiClient.post<ExchangeRequest>(`/api/v1/exchange/requests/${id}/cancel`);
export const retailerOpenRfqs = () => apiClient.get<{ items: ExchangeRequest[]; total: number }>("/api/v1/retailer/exchange/requests");
export const retailerSubmitRfqBid = (id: UUID, body: { lines: { manifest_index: number; listing_id: UUID; unit_price_paise: number }[]; estimated_delivery_hours: number; notes?: string }) =>
  apiClient.post<ExchangeBid>(`/api/v1/retailer/exchange/requests/${id}/bids`, body);
export const retailerWithdrawRfqBid = (id: UUID) => apiClient.delete<void>(`/api/v1/retailer/exchange/requests/${id}/bids`);

// ---------------------------------------------------------------- 3D AI Negotiator
export interface NegotiationSession {
  id: UUID; status: "IN_PROGRESS" | "ACCEPTED" | "REJECTED" | "EXPIRED"; language: string; language_fallback: boolean;
  current_round: number; max_rounds: number; list_total_paise: number; current_offer_paise: number; savings_paise: number;
  final_accepted_price_paise: number | null; within_budget: boolean | null;
  lines: { listing_id: UUID; product_name: string; quantity: number; list_unit_price_paise: number; offer_unit_price_paise: number; negotiable: boolean }[];
  messages: { role: "assistant" | "customer"; text: string; at: string }[];
  expires_at: string; quote_id: UUID | null; quote_total_payable_paise: number | null; quote_expires_at: string | null;
}
export const startNegotiation = (body: { target_price_paise?: number; max_budget_paise?: number; language?: string } = {}) =>
  apiClient.post<NegotiationSession>("/api/v1/negotiate/start", body);
export const counterOffer = (sessionId: UUID, proposedPricePaise: number) =>
  apiClient.post<NegotiationSession>("/api/v1/negotiate/counter-offer", { session_id: sessionId, proposed_price_paise: proposedPricePaise });
export const acceptNegotiation = (sessionId: UUID) => apiClient.post<NegotiationSession>("/api/v1/negotiate/accept", { session_id: sessionId });
export interface NegotiationRule { id: UUID; listing_id: UUID | null; min_floor_price_paise: number | null; max_auto_discount_percent: number; bundle_quantity_threshold: number | null; bundle_extra_discount_percent: number; is_active: boolean; created_at: string }
export const listNegotiationRules = () => apiClient.get<NegotiationRule[]>("/api/v1/retailer/negotiation-rules");
export const upsertNegotiationRule = (body: Omit<NegotiationRule, "id" | "created_at" | "listing_id" | "min_floor_price_paise" | "bundle_quantity_threshold"> & { listing_id?: UUID | null; min_floor_price_paise?: number | null; bundle_quantity_threshold?: number | null }) =>
  apiClient.put<NegotiationRule>("/api/v1/retailer/negotiation-rules", body);
export const deleteNegotiationRule = (id: UUID) => apiClient.delete<void>(`/api/v1/retailer/negotiation-rules/${id}`);

// ---------------------------------------------------------------- 3E Dukaan vs Dukaan
export interface AuctionBid { id: UUID; rank: number; retailer_id: UUID; retailer_name: string; retailer_rating: number; bid_price_paise: number; savings_paise: number; delivery_eta_minutes: number; warranty_note: string | null; is_simulated?: boolean; created_at: string }
export interface Auction {
  id: UUID; status: "ACTIVE" | "COMPLETED" | "NO_BIDS" | "AWARDED" | "CANCELLED"; pincode: string;
  items: { variant_id: UUID; product_name: string; variant_name: string; quantity: number; reference_unit_price_paise: number }[];
  reference_total_paise: number; duration_seconds: number; starts_at: string; ends_at: string; seconds_remaining: number;
  bid_count: number; best_bid_paise: number | null; winning_bid_id: UUID | null; bids: AuctionBid[] | null;
  my_best_bid_paise: number | null; my_list_total_paise: number | null;
  // Retailer view only: own position, outbid state, anonymised price ladder, outcome.
  my_rank?: number | null; competing_stores?: number | null; is_winning?: boolean | null; outbid?: boolean | null;
  bid_ladder?: { price_paise: number; at: string; mine: boolean }[] | null;
  my_outcome?: "WON" | "NOT_SELECTED" | "AWAITING_CHOICE" | "CLOSED" | null;
}
export const startAuction = (pincode: string) => apiClient.post<Auction>("/api/v1/auctions/start", { pincode });
export const getActiveAuction = () => apiClient.get<Auction | null>("/api/v1/auctions/active");
export const getAuctionLive = (id: UUID) => apiClient.get<Auction>(`/api/v1/auctions/${id}/live`);
/** Server-Sent Events URL (use with EventSource; events: "auction" and "end"). */
export const auctionEventStreamPath = (id: UUID) => `/api/v1/auctions/${id}/live`;
export const acceptAuctionBid = (id: UUID, bidId: UUID) =>
  apiClient.post<{ auction: Auction; cart_id: UUID; message: string }>(`/api/v1/auctions/${id}/accept`, { bid_id: bidId });
export const cancelAuction = (id: UUID) => apiClient.post<Auction>(`/api/v1/auctions/${id}/cancel`);
export const retailerLiveAuctions = () => apiClient.get<{ items: Auction[]; total: number }>("/api/v1/retailer/auctions");
export const retailerRecentAuctions = () => apiClient.get<{ items: Auction[]; total: number }>("/api/v1/retailer/auctions/recent");
export const retailerBid = (id: UUID, body: { bid_price_paise: number; delivery_eta_minutes: number; warranty_note?: string }) =>
  apiClient.post<AuctionBid>(`/api/v1/retailer/auctions/${id}/bid`, body);
export const retailerSimulateBid = (id: UUID) =>
  apiClient.post<AuctionBid>(`/api/v1/retailer/auctions/${id}/simulate`, {});

// ---------------------------------------------------------------- 3I Handwritten List to Basket
export interface ParsedListItem {
  line: string; name: string; interpreted_as: string; size: string | null; quantity: number;
  candidates: { listing_id: UUID; product_id: UUID; product_name: string; retailer_name: string; price_paise: number; in_stock: boolean }[];
  suggested_listing_id: UUID | null;
  /** Provider-reported recognition confidence for this line, 0–1 (photo uploads only). */
  ocr_confidence?: number | null;
  /** True when the line was read with low confidence and should be checked. */
  needs_review?: boolean;
}
export interface ParseListResult {
  source: "OCR" | "TEXT"; provider: string | null; raw_text: string; items: ParsedListItem[]; unmatched_count: number;
  ocr_confidence?: number | null;
  /** True when no OCR provider is configured and the text must be typed. */
  manual_entry?: boolean;
}
export const parseShoppingList = (body: { text: string } | { image_base64: string; content_type: "image/jpeg" | "image/png" | "image/webp" }) =>
  apiClient.post<ParseListResult>("/api/v1/vision/parse-list", body);
export const buildCartFromList = (items: { listing_id: UUID; quantity: number }[]) =>
  apiClient.post<{ cart_id: UUID; added: number; skipped: { listing_id: UUID; reason: string; available?: number }[] }>("/api/v1/vision/build-cart", { items });
