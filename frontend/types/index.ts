export interface ApiErrorDetail {
  loc?: (string | number)[];
  msg?: string;
  type?: string;
  [key: string]: unknown;
}

export interface ApiErrorEnvelope {
  error: {
    code: string;
    message: string;
    request_id?: string;
    details?: ApiErrorDetail[];
  };
}

export interface HealthResponse {
  status: "ok" | "degraded" | "down";
  service: string;
  environment: string;
}

export interface ReadyResponse {
  status: "ready" | "degraded" | "not_ready";
  service: string;
  checks: {
    database: {
      status: "connected" | "unconfigured" | "unreachable" | "error";
      message?: string;
    };
    [key: string]: unknown;
  };
}

export interface ApiInfoResponse {
  project: string;
  version: string;
  environment: string;
}

// Catalogue types
export interface Category {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  image_url?: string | null;
  icon?: string | null;
  parent_id?: string | null;
  product_count: number;
}

export interface Retailer {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  logo_url?: string | null;
  rating: number;
  is_active: boolean;
}

export interface ProductImage {
  id: string;
  url: string;
  alt_text?: string | null;
  is_primary: boolean;
  sort_order: number;
  variant_id?: string | null;
}

export interface ProductListingDetail {
  id: string;
  retailer_id: string;
  retailer_name: string;
  retailer_rating: number;
  retailer_state?: string | null;
  seller_sku?: string | null;
  original_price_paise: number;
  selling_price_paise: number;
  currency: string;
  is_active: boolean;
  on_hand_quantity: number;
  reserved_quantity: number;
  available_quantity: number;
  is_in_stock: boolean;
}

export interface ProductVariantDetail {
  id: string;
  product_id: string;
  name: string;
  sku: string;
  attributes: Record<string, string | number | boolean>;
  is_active: boolean;
  listings: ProductListingDetail[];
  min_price_paise?: number | null;
  is_in_stock: boolean;
}

export interface ProductSummary {
  id: string;
  name: string;
  slug: string;
  brand: string;
  category_id: string;
  category_name: string;
  category_slug: string;
  primary_image?: string | null;
  min_price_paise: number;
  max_price_paise: number;
  original_price_paise?: number | null;
  currency: string;
  is_in_stock: boolean;
  variant_count: number;
  retailer_count: number;
}

export interface ProductListResponse {
  items: ProductSummary[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface ProductDetail {
  id: string;
  name: string;
  slug: string;
  brand: string;
  description?: string | null;
  category_id: string;
  category_name: string;
  category_slug: string;
  images: ProductImage[];
  variants: ProductVariantDetail[];
  min_price_paise: number;
  max_price_paise: number;
  original_price_paise?: number | null;
  currency: string;
  is_in_stock: boolean;
  total_available_stock: number;
}

export interface ProductFilterParams {
  category_slug?: string;
  category_id?: string;
  retailer_id?: string;
  brand?: string;
  search?: string;
  min_price?: number;
  max_price?: number;
  in_stock?: boolean;
  sort_by?: "newest" | "price_asc" | "price_desc" | "name_asc";
  page?: number;
  limit?: number;
}

// Identity, Authentication & Session Types
export interface User {
  id: string;
  email: string;
  phone?: string | null;
  full_name: string;
  role: "customer" | "retailer" | "admin" | string;
  is_active: boolean;
  retailer_id?: string | null;
  store_name?: string | null;
  verification_status?: "PENDING" | "VERIFIED" | "SUSPENDED" | string | null;
  created_at: string;
}

export interface RetailerProfile {
  id: string;
  user_id: string | null;
  name: string;
  slug: string;
  description: string | null;
  logo_url: string | null;
  rating: number;
  state: string | null;
  business_address: string | null;
  contact_phone: string | null;
  contact_email: string | null;
  business_hours: Record<string, string> | null;
  policies: Record<string, string> | null;
  is_open: boolean;
  verification_status: "PENDING" | "VERIFIED" | "SUSPENDED" | string;
  is_active: boolean;
  created_at: string;
  updated_at?: string | null;
}

export interface RetailerOverview {
  retailer_id: string;
  store_name: string;
  slug: string;
  state: string | null;
  is_open: boolean;
  verification_status: string;
  rating: number;
  total_listings: number;
  active_listings: number;
  total_inventory_units: number;
  low_stock_alerts: number;
  out_of_stock_alerts: number;
  recent_orders_count: number;
}

export interface CatalogueLookupVariant {
  id: string;
  name: string;
  sku: string;
  attributes: Record<string, any>;
  is_active: boolean;
  is_already_listed: boolean;
  existing_listing_id?: string | null;
}

export interface CatalogueLookupProduct {
  id: string;
  name: string;
  brand: string;
  category_id: string;
  category_name: string;
  description: string | null;
  image_url: string | null;
  variants: CatalogueLookupVariant[];
}

export interface RetailerListingInventory {
  on_hand_quantity: number;
  reserved_quantity: number;
  available_quantity: number;
  low_stock_threshold: number;
  is_low_stock: boolean;
  is_out_of_stock: boolean;
}

export interface RetailerListingItem {
  id: string;
  retailer_id: string;
  variant_id: string;
  product_id: string;
  product_name: string;
  brand: string;
  category_name: string;
  variant_name: string;
  variant_sku: string;
  variant_attributes: Record<string, any>;
  seller_sku: string | null;
  original_price_paise: number;
  selling_price_paise: number;
  currency: string;
  hsn_code: string | null;
  gst_rate_basis_points: number | null;
  is_tax_verified: boolean;
  is_active: boolean;
  image_url: string | null;
  inventory: RetailerListingInventory;
  created_at: string;
  updated_at: string;
}

export interface RetailerListingCreatePayload {
  variant_id: string;
  seller_sku?: string;
  original_price_paise: number;
  selling_price_paise: number;
  hsn_code?: string;
  gst_rate_basis_points?: number;
  is_active?: boolean;
  initial_on_hand_quantity: number;
  low_stock_threshold?: number;
}

export interface RetailerListingUpdatePayload {
  seller_sku?: string | null;
  original_price_paise?: number;
  selling_price_paise?: number;
  hsn_code?: string | null;
  gst_rate_basis_points?: number | null;
  is_active?: boolean;
  low_stock_threshold?: number;
}

export interface RetailerInventoryItem {
  listing_id: string;
  product_name: string;
  variant_name: string;
  sku: string;
  seller_sku: string | null;
  selling_price_paise: number;
  on_hand_quantity: number;
  reserved_quantity: number;
  available_quantity: number;
  low_stock_threshold: number;
  is_low_stock: boolean;
  is_out_of_stock: boolean;
  is_active: boolean;
  updated_at: string;
}

export interface InventorySummaryStats {
  total_items: number;
  total_on_hand_units: number;
  total_reserved_units: number;
  total_available_units: number;
  low_stock_count: number;
  out_of_stock_count: number;
}

export interface RetailerInventoryDashboard {
  summary: InventorySummaryStats;
  items: RetailerInventoryItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface RetailerInventoryAdjustmentPayload {
  adjustment_type: "SET" | "DELTA";
  quantity: number;
  low_stock_threshold?: number;
  reason?: string;
}

export interface AdminOverview {
  total_orders: number;
  total_revenue_paise: number;
  total_customers: number;
  total_retailers: number;
  pending_verifications: number;
  active_products: number;
}

export interface AdminRetailerListItem {
  id: string;
  name: string;
  slug: string;
  state: string | null;
  verification_status: "PENDING" | "VERIFIED" | "SUSPENDED" | "REJECTED" | string;
  is_active: boolean;
  is_open: boolean;
  business_address: string | null;
  contact_phone: string | null;
  contact_email: string | null;
  owner_name: string | null;
  owner_email: string | null;
  documents_count?: number;
  created_at: string;
}

export interface RetailerDocumentItem {
  id: string;
  document_type: string;
  document_url: string;
  status: "PENDING" | "VERIFIED" | "REJECTED" | string;
  rejection_reason?: string | null;
  created_at: string;
  updated_at: string;
}

export interface RetailerVerificationHistoryItem {
  id: string;
  action: string;
  from_status: string;
  to_status: string;
  reason?: string | null;
  admin_id?: string | null;
  created_at: string;
}

export interface AdminRetailerDetailResponse extends AdminRetailerListItem {
  description?: string | null;
  logo_url?: string | null;
  rating: number;
  reviewed_by_user_id?: string | null;
  verified_at?: string | null;
  rejection_reason?: string | null;
  documents: RetailerDocumentItem[];
  verification_history: RetailerVerificationHistoryItem[];
}

export interface AdminRetailerSalesProductItem {
  product_id: string;
  product_name: string;
  variant_id: string;
  variant_name: string;
  sku: string | null;
  quantity_sold: number;
  selling_price_paise: number;
  gross_revenue_paise: number;
  refund_quantity: number;
  refund_amount_paise: number;
  net_sales_paise: number;
}

export interface AdminRetailerSalesAnalyticsResponse {
  retailer_id: string;
  retailer_name: string;
  state: string | null;
  verification_status: string;
  is_active: boolean;
  total_orders: number;
  total_units_sold: number;
  gross_merchandise_value_paise: number;
  refunded_amount_paise: number;
  net_sales_paise: number;
  currency: string;
  product_sales: AdminRetailerSalesProductItem[];
}

export interface AdminCatalogueVariantItem {
  id: string;
  product_id: string;
  name: string;
  sku: string;
  attributes: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
  listings_count: number;
}

export interface AdminCatalogueProductListItem {
  id: string;
  name: string;
  slug: string;
  brand: string;
  category_id: string;
  category_name?: string | null;
  is_active: boolean;
  variants_count: number;
  listings_count: number;
  primary_image_url?: string | null;
  created_at: string;
}

export interface AdminCatalogueProductDetailResponse {
  id: string;
  name: string;
  slug: string;
  brand: string;
  category_id: string;
  category_name?: string | null;
  description?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  images: Array<{
    id: string;
    url: string;
    alt_text?: string | null;
    is_primary: boolean;
    sort_order: number;
  }>;
  variants: AdminCatalogueVariantItem[];
  active_listings_count: number;
}

export interface AdminCatalogueVariantCreatePayload {
  name: string;
  sku: string;
  attributes?: Record<string, unknown>;
  is_active?: boolean;
}

export interface AdminCatalogueVariantUpdatePayload {
  name?: string;
  sku?: string;
  attributes?: Record<string, unknown>;
  is_active?: boolean;
}

export interface AdminCatalogueProductCreatePayload {
  category_id: string;
  name: string;
  slug?: string;
  brand: string;
  description?: string;
  is_active?: boolean;
  image_urls?: string[];
  variants?: AdminCatalogueVariantCreatePayload[];
}

export interface AdminCatalogueProductUpdatePayload {
  category_id?: string;
  name?: string;
  slug?: string;
  brand?: string;
  description?: string;
  is_active?: boolean;
}

export interface AdminCategoryCreatePayload {
  name: string;
  slug?: string;
  description?: string;
  image_url?: string;
  icon?: string;
  parent_id?: string | null;
  is_active?: boolean;
}

export interface AdminCategoryListItem {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  image_url?: string | null;
  icon?: string | null;
  parent_id?: string | null;
  parent_name?: string | null;
  is_active: boolean;
  product_count: number;
  children: AdminCategoryListItem[];
}

export interface AdminDealListItem {
  id: string;
  name: string;
  code?: string | null;
  discount_type: "PERCENTAGE" | "FIXED_AMOUNT" | string;
  discount_value: number;
  scope: "PLATFORM_WIDE" | "CATEGORY" | "PRODUCT" | "LISTING" | string;
  category_id?: string | null;
  category_name?: string | null;
  product_id?: string | null;
  product_name?: string | null;
  listing_id?: string | null;
  min_order_paise: number;
  max_discount_paise?: number | null;
  usage_limit?: number | null;
  times_used: number;
  is_active: boolean;
  valid_from: string;
  valid_to?: string | null;
  status: "ACTIVE" | "SCHEDULED" | "EXPIRED" | "PAUSED" | string;
  created_at: string;
}

export interface AdminDealDetailResponse extends AdminDealListItem {
  description?: string | null;
  updated_at: string;
}

export interface AdminDealCreatePayload {
  name: string;
  code?: string;
  discount_type: "PERCENTAGE" | "FIXED_AMOUNT";
  discount_value: number;
  scope?: "PLATFORM_WIDE" | "CATEGORY" | "PRODUCT" | "LISTING";
  category_id?: string;
  product_id?: string;
  listing_id?: string;
  min_order_paise?: number;
  max_discount_paise?: number;
  usage_limit?: number;
  valid_from?: string;
  valid_to?: string;
  description?: string;
  is_active?: boolean;
}

export interface AdminDealUpdatePayload {
  name?: string;
  code?: string;
  discount_type?: "PERCENTAGE" | "FIXED_AMOUNT";
  discount_value?: number;
  min_order_paise?: number;
  max_discount_paise?: number;
  usage_limit?: number;
  valid_from?: string;
  valid_to?: string;
  description?: string;
  is_active?: boolean;
}

export interface RetailerRegisterPayload {
  email: string;
  password: string;
  full_name: string;
  phone: string;
  store_name: string;
  state: string;
  business_address: string;
  contact_email?: string;
  contact_phone?: string;
  description?: string;
}

export interface AuthResponse {
  user: User;
  access_token: string;
  refresh_token: string;
  csrf_token: string;
  token_type: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  csrf_token: string;
  token_type: string;
}

export interface MessageResponse {
  message: string;
}

// Address Management Types
export interface Address {
  id: string;
  user_id: string;
  recipient_name: string;
  phone: string;
  line1: string;
  line2?: string | null;
  city: string;
  state: string;
  postal_code: string;
  landmark?: string | null;
  is_default: boolean;
  created_at: string;
}

export interface AddressCreatePayload {
  recipient_name: string;
  phone: string;
  line1: string;
  line2?: string | null;
  city: string;
  state: string;
  postal_code: string;
  landmark?: string | null;
  is_default?: boolean;
}

export interface AddressUpdatePayload {
  recipient_name?: string;
  phone?: string;
  line1?: string;
  line2?: string | null;
  city?: string;
  state?: string;
  postal_code?: string;
  landmark?: string | null;
  is_default?: boolean;
}

// Cart types
export interface CartItem {
  id: string;
  listing_id: string;
  variant_id: string;
  product_id: string;
  product_name: string;
  product_slug: string;
  variant_name?: string | null;
  attributes: Record<string, unknown>;
  primary_image_url?: string | null;
  retailer_id: string;
  retailer_name: string;
  retailer_rating?: number | null;
  unit_price_paise: number;
  quantity: number;
  subtotal_paise: number;
  available_stock: number;
  is_available: boolean;
  validation_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface CartRetailerSummary {
  retailer_id: string;
  retailer_name: string;
  item_count: number;
  subtotal_paise: number;
}

export interface Cart {
  id: string;
  status: string;
  currency: string;
  items: CartItem[];
  item_count: number;
  total_quantity: number;
  subtotal_paise: number;
  retailers: CartRetailerSummary[];
  warnings: string[];
  created_at: string;
  updated_at: string;
}

export interface CartItemAddPayload {
  listing_id: string;
  quantity?: number;
}

export interface CartItemUpdatePayload {
  quantity: number;
}

export interface CartMergePayload {
  guest_token?: string;
}

export interface CartMergeResponse {
  cart: Cart;
  migrated_items_count: number;
  warnings: string[];
}

// Pricing & Quote Types (Phase 2C)
export type QuoteStatus = 'ACTIVE' | 'CONSUMED' | 'EXPIRED' | 'SUPERSEDED';

export interface TaxBreakdown {
  hsn_code: string;
  gst_rate_basis_points: number;
  gst_rate_percentage: number;
  taxable_base_paise: number;
  cgst_paise: number;
  sgst_paise: number;
  igst_paise: number;
  total_tax_paise: number;
  is_intra_state: boolean;
}

export interface RetailerPricingBreakdown {
  retailer_id: string;
  retailer_name: string;
  retailer_state: string;
  subtotal_paise: number;
  delivery_fee_paise: number;
  free_delivery_threshold_paise: number;
  qualifies_for_free_delivery: boolean;
  amount_needed_for_free_delivery_paise: number;
}

export interface QuoteItem {
  id: string;
  listing_id: string;
  variant_id: string;
  retailer_id: string;
  product_title: string;
  variant_title: string;
  sku?: string | null;
  hsn_code: string;
  gst_rate_basis_points: number;
  quantity: number;
  unit_original_price_paise: number;
  unit_selling_price_paise: number;
  unit_discount_paise: number;
  unit_discounted_price_paise: number;
  total_selling_price_paise: number;
  taxable_base_paise: number;
  cgst_paise: number;
  sgst_paise: number;
  igst_paise: number;
  total_tax_paise: number;
  retailer_name: string;
  retailer_state: string;
  created_at: string;
}

export interface Quote {
  id: string;
  customer_id?: string | null;
  cart_id?: string | null;
  delivery_address_id?: string | null;
  delivery_state?: string | null;
  subtotal_paise: number;
  discount_total_paise: number;
  delivery_fee_paise: number;
  cgst_paise: number;
  sgst_paise: number;
  igst_paise: number;
  total_tax_paise: number;
  total_payable_paise: number;
  currency: string;
  status: QuoteStatus;
  is_consumed: boolean;
  consumed_at?: string | null;
  expires_at: string;
  superseded_by_quote_id?: string | null;
  created_at: string;
  updated_at: string;
  items: QuoteItem[];
  retailer_breakdowns: RetailerPricingBreakdown[];
}

export interface QuoteCreatePayload {
  delivery_address_id?: string | null;
  delivery_state?: string | null;
}

export interface QuoteValidationIssue {
  code: string;
  message: string;
  listing_id?: string | null;
  previous_value?: unknown;
  current_value?: unknown;
}

export interface QuoteValidationResult {
  valid: boolean;
  reason?: string | null;
  message: string;
  can_refresh: boolean;
  issues: QuoteValidationIssue[];
  quote: Quote;
}

// Phase 2D: Inventory Reservations & Concurrency Protection
export type ReservationStatus =
  | "ACTIVE"
  | "ALLOCATED_TO_ORDER"
  | "CONFIRMED"
  | "RELEASED"
  | "EXPIRED";

export interface ReservationItem {
  id: string;
  listing_id: string;
  retailer_id: string;
  variant_id: string;
  quantity: number;
}

export interface Reservation {
  id: string;
  quote_id: string;
  customer_id?: string | null;
  status: ReservationStatus;
  idempotency_key?: string | null;
  expires_at: string;
  seconds_remaining: number;
  is_expired: boolean;
  items: ReservationItem[];
  created_at: string;
  updated_at: string;
}

export interface ReservationCreatePayload {
  quote_id: string;
  idempotency_key?: string | null;
}

export interface ReservationReleaseResponse {
  id: string;
  status: ReservationStatus;
  released_at?: string | null;
  release_reason?: string | null;
}

// Phase 2E & Phase 4: Orders, Post-Purchase, Tracking & Returns
export type OrderStatus =
  | "PENDING_PAYMENT"
  | "CONFIRMED"
  | "PROCESSING"
  | "PACKED"
  | "SHIPPED"
  | "OUT_FOR_DELIVERY"
  | "DELIVERED"
  | "CANCELLED"
  | "RETURNED";

export type ShipmentStatus =
  | "LABEL_CREATED"
  | "PICKED_UP"
  | "IN_TRANSIT"
  | "OUT_FOR_DELIVERY"
  | "DELIVERED"
  | "EXCEPTION"
  | "CANCELLED";

export type ReturnStatus =
  | "REQUESTED"
  | "APPROVED"
  | "REJECTED"
  | "PICKUP_PENDING"
  | "RECEIVED"
  | "INSPECTED"
  | "REFUND_PENDING"
  | "REFUNDED"
  | "CANCELLED";

export type PaymentStatus =
  | "NOT_INITIATED"
  | "PENDING"
  | "PAID"
  | "SUCCEEDED"
  | "PARTIALLY_REFUNDED"
  | "REFUNDED"
  | "FAILED"
  | "REQUIRES_RECONCILIATION";

export interface DeliveryAddressSnapshot {
  full_name: string;
  address_line1: string;
  address_line2?: string | null;
  city: string;
  state: string;
  postal_code: string;
  phone: string;
}

export interface OrderItem {
  id: string;
  listing_id: string;
  variant_id: string;
  retailer_id: string;
  product_title: string;
  variant_title?: string | null;
  sku?: string | null;
  hsn_code?: string | null;
  gst_rate_basis_points: number;
  quantity: number;
  unit_original_price_paise: number;
  unit_selling_price_paise: number;
  unit_discount_paise: number;
  unit_discounted_price_paise: number;
  total_selling_price_paise: number;
  taxable_base_paise: number;
  cgst_paise: number;
  sgst_paise: number;
  igst_paise: number;
  total_tax_paise: number;
  retailer_name: string;
  retailer_state: string;
  created_at: string;
}

export interface OrderStatusHistoryEntry {
  id: string;
  from_status?: string | null;
  to_status: string;
  reason?: string | null;
  created_at: string;
}

export interface ShipmentItem {
  id: string;
  order_item_id: string;
  quantity: number;
  created_at: string;
}

export interface Shipment {
  id: string;
  order_id: string;
  shipment_number: string;
  carrier_name: string;
  carrier_code: string;
  tracking_number: string;
  tracking_url?: string | null;
  status: ShipmentStatus;
  shipped_at?: string | null;
  estimated_delivery_at?: string | null;
  delivered_at?: string | null;
  notes?: string | null;
  carrier_event_history: Array<{
    status: string;
    description: string;
    location?: string | null;
    timestamp: string;
  }>;
  created_at: string;
  items: ShipmentItem[];
}

export interface ReturnItem {
  id: string;
  order_item_id: string;
  quantity: number;
  refund_subtotal_paise: number;
  condition_grade?: string | null;
  restock_approved: boolean;
  created_at: string;
}

export interface ReturnStatusHistoryEntry {
  id: string;
  from_status?: string | null;
  to_status: string;
  reason?: string | null;
  actor: string;
  created_at: string;
}

export interface OrderReturn {
  id: string;
  order_id: string;
  return_number: string;
  status: ReturnStatus;
  reason: string;
  customer_notes?: string | null;
  admin_notes?: string | null;
  refund_amount_paise: number;
  payment_refund_id?: string | null;
  requested_at: string;
  inspected_at?: string | null;
  resolved_at?: string | null;
  created_at: string;
  items: ReturnItem[];
  status_history?: ReturnStatusHistoryEntry[];
}

export interface CustomerNotification {
  id: string;
  order_id?: string | null;
  title: string;
  message: string;
  event_type: string;
  is_read: boolean;
  read_at?: string | null;
  created_at: string;
}

export interface NotificationListResponse {
  items: CustomerNotification[];
  unread_count: number;
}

export interface OrderTrackingTimelineEvent {
  status: string;
  title: string;
  description: string;
  timestamp?: string | null;
  completed: boolean;
  current: boolean;
}

export interface OrderTrackingResponse {
  order_id: string;
  order_number: string;
  order_status: OrderStatus;
  carrier_name?: string | null;
  carrier_code?: string | null;
  tracking_number?: string | null;
  tracking_url?: string | null;
  estimated_delivery_at?: string | null;
  delivered_at?: string | null;
  shipments: Shipment[];
  timeline: OrderTrackingTimelineEvent[];
}

export interface Order {
  id: string;
  order_number: string;
  customer_id?: string | null;
  is_guest?: boolean;
  quote_id: string;
  reservation_id: string;
  delivery_address: DeliveryAddressSnapshot;
  subtotal_paise: number;
  discount_total_paise: number;
  delivery_fee_paise: number;
  cgst_paise: number;
  sgst_paise: number;
  igst_paise: number;
  total_tax_paise: number;
  total_payable_paise: number;
  currency: string;
  status: OrderStatus;
  payment_status: PaymentStatus;
  guest_access_token?: string | null;
  cancellation_reason?: string | null;
  cancelled_at?: string | null;
  delivered_at?: string | null;
  fulfilling_capture_id?: string | null;
  payment_window_expires_at?: string | null;
  items: OrderItem[];
  status_history?: OrderStatusHistoryEntry[];
  shipments?: Shipment[];
  returns?: OrderReturn[];
  created_at: string;
  updated_at?: string;
}

export interface OrderListItem {
  id: string;
  order_number: string;
  status: OrderStatus;
  payment_status: PaymentStatus;
  total_payable_paise: number;
  currency: string;
  item_count?: number;
  cancellation_reason?: string | null;
  cancelled_at?: string | null;
  delivered_at?: string | null;
  created_at: string;
}

export interface OrderCancellationRequest {
  reason: string;
  idempotency_key?: string | null;
}

export interface OrderCancellationResponse {
  order_id: string;
  order_number: string;
  status: string;
  cancelled_at: string;
  refund_status?: string | null;
  refund_amount_paise?: number | null;
  inventory_restocked: boolean;
  message: string;
}

export interface ReturnCreateRequest {
  reason: string;
  customer_notes?: string | null;
  items: Array<{ order_item_id: string; quantity: number }>;
  idempotency_key?: string | null;
}

export interface CreateOrderRequest {
  quote_id?: string;
  reservation_id: string;
  delivery_address_id?: string | null;
  delivery_address?: {
    full_name: string;
    address_line1: string;
    address_line2?: string | null;
    city: string;
    state: string;
    postal_code: string;
    phone: string;
  } | null;
  idempotency_key?: string | null;
}

export interface OrderListResponse {
  items?: OrderListItem[];
  total: number;
  orders: OrderListItem[];
}

// Phase 2F: Razorpay Payments, Capture & Refunds
export type PaymentAttemptStatus =
  | "CREATING"
  | "PENDING"
  | "AUTHORIZED"
  | "CAPTURED"
  | "FAILED"
  | "UNKNOWN"
  | "REQUIRES_RECONCILIATION";

export type CaptureStatus = "CAPTURED" | "FAILED" | "ANOMALOUS";

export type RefundStatus = "PENDING" | "PROCESSED" | "FAILED";

export interface PaymentInitiateResponse {
  payment_id: string;
  order_id: string;
  provider_order_id: string;
  amount_paise: number;
  currency: string;
  razorpay_key_id: string;
  attempt_status: PaymentAttemptStatus;
  notes?: Record<string, unknown> | null;
  created_at: string;
}

export interface PaymentVerifyRequest {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}

export interface PaymentVerifyResponse {
  payment_id?: string;
  order_id: string;
  order_number?: string;
  status: OrderStatus;
  order_status?: OrderStatus;
  payment_status: PaymentStatus;
  fulfilling_capture_id?: string | null;
  amount_paid_paise?: number;
  amount_paise?: number;
  currency?: string;
  message?: string;
  confirmed_at?: string;
}

export interface PaymentRefundRequest {
  amount_paise: number;
  reason?: string | null;
}

export interface PaymentRefundResponse {
  refund_id: string;
  payment_id: string;
  order_id: string;
  provider_refund_id?: string | null;
  amount_paise: number;
  currency: string;
  status: RefundStatus;
  reason?: string | null;
  created_at: string;
}

export interface RazorpayPaymentSuccessResponse {
  razorpay_payment_id: string;
  razorpay_order_id: string;
  razorpay_signature: string;
}

export interface RazorpayErrorResponse {
  code: string;
  description: string;
  source: string;
  step: string;
  reason: string;
  metadata: {
    order_id: string;
    payment_id: string;
  };
}

export interface RazorpayCheckoutOptions {
  key: string;
  amount: number;
  currency: string;
  name: string;
  description?: string;
  image?: string;
  order_id: string;
  handler?: (response: RazorpayPaymentSuccessResponse) => void;
  prefill?: {
    name?: string;
    email?: string;
    contact?: string;
  };
  notes?: Record<string, unknown>;
  theme?: {
    color?: string;
  };
  modal?: {
    ondismiss?: () => void;
    escape?: boolean;
    backdropclose?: boolean;
  };
}

// Universal Search Types (Phase 3E)
export interface SearchFacetBucket {
  key: string;
  doc_count: number;
}

export interface SearchFacets {
  categories: SearchFacetBucket[];
  brands: SearchFacetBucket[];
  retailers: SearchFacetBucket[];
  price_stats?: {
    count?: number;
    min?: number;
    max?: number;
    avg?: number;
    sum?: number;
  };
}

export interface ProductSearchItem {
  product_id: string;
  name: string;
  slug: string;
  brand: string;
  description: string;
  category_id: string;
  category_name: string;
  category_slug: string;
  primary_image_url?: string | null;
  min_price_paise: number;
  max_price_paise: number;
  currency: string;
  is_in_stock: boolean;
  total_available_quantity: number;
  rating: number;
  retailers: Array<{
    retailer_id: string;
    retailer_name: string;
    listing_id: string;
    selling_price_paise: number;
    original_price_paise: number;
    is_in_stock: boolean;
    available_quantity: number;
  }>;
  variants: Array<{
    variant_id: string;
    name: string;
    sku: string;
    attributes: Record<string, unknown>;
    is_in_stock: boolean;
  }>;
  attributes: Record<string, string[]>;
}

export interface SearchResponse {
  items: ProductSearchItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  engine: "opensearch" | "postgres_fallback";
  facets?: SearchFacets | null;
  took_ms?: number;
}

export interface SuggestionItem {
  text: string;
  type: "product" | "brand" | "category";
  slug?: string | null;
}

export interface SuggestionsResponse {
  query: string;
  suggestions: SuggestionItem[];
}

export interface SearchFilterParams {
  q?: string;
  category?: string;
  brand?: string;
  retailer_id?: string;
  min_price?: number;
  max_price?: number;
  in_stock?: boolean;
  sort?: "relevance" | "price_asc" | "price_desc" | "rating_desc" | "newest";
  page?: number;
  page_size?: number;
  force_fallback?: boolean;
}

// ================= Phase 1 Retailer Portal Extensions =================

export interface RetailerProductCreatePayload {
  name: string;
  brand: string;
  category_id: string;
  description?: string;
  image_url?: string;
  variant_name?: string;
  sku: string;
  seller_sku?: string;
  original_price_paise: number;
  selling_price_paise: number;
  hsn_code?: string;
  gst_rate_basis_points?: number;
  initial_on_hand_quantity?: number;
  low_stock_threshold?: number;
  is_active?: boolean;
}

export interface RetailerOrderItem {
  id: string;
  order_id: string;
  listing_id: string;
  variant_id: string;
  product_title: string;
  variant_title: string;
  sku?: string | null;
  quantity: number;
  unit_selling_price_paise: number;
  total_selling_price_paise: number;
  total_tax_paise: number;
  created_at: string;
}

export interface RetailerOrderListItem {
  id: string;
  order_number: string;
  status: string;
  payment_status: string;
  customer_name: string;
  delivery_city?: string | null;
  delivery_state?: string | null;
  total_items: number;
  retailer_subtotal_paise: number;
  retailer_tax_paise: number;
  retailer_total_paise: number;
  created_at: string;
  items: RetailerOrderItem[];
}

export interface RetailerOrderListResponse {
  items: RetailerOrderListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface RetailerOrderDetailResponse {
  id: string;
  order_number: string;
  status: string;
  payment_status: string;
  customer_name: string;
  delivery_address: Record<string, any>;
  items: RetailerOrderItem[];
  retailer_subtotal_paise: number;
  retailer_tax_paise: number;
  retailer_total_paise: number;
  created_at: string;
  status_history: Array<{
    from_status?: string | null;
    to_status: string;
    reason?: string | null;
    created_at?: string | null;
  }>;
}

export interface RetailerOrderStatusUpdatePayload {
  status: string;
  reason?: string;
}

export interface RetailerOfferItem {
  id: string;
  code?: string | null;
  name: string;
  description?: string | null;
  discount_type: "PERCENTAGE" | "FIXED_AMOUNT";
  discount_value: number;
  listing_id?: string | null;
  min_order_paise: number;
  max_discount_paise?: number | null;
  is_active: boolean;
  valid_from: string;
  valid_to?: string | null;
}

export interface RetailerOfferCreatePayload {
  code?: string;
  name: string;
  description?: string;
  discount_type: "PERCENTAGE" | "FIXED_AMOUNT";
  discount_value: number;
  listing_id?: string;
  min_order_paise?: number;
  max_discount_paise?: number;
  is_active?: boolean;
  valid_to?: string;
}

export interface RetailerOfferUpdatePayload {
  name?: string;
  description?: string;
  discount_value?: number;
  min_order_paise?: number;
  max_discount_paise?: number;
  is_active?: boolean;
  valid_to?: string;
}

export interface RetailerAnalyticsProductItem {
  listing_id: string;
  product_name: string;
  variant_sku: string;
  units_sold: number;
  revenue_paise: number;
}

export interface RetailerAnalyticsResponse {
  total_revenue_paise: number;
  total_orders: number;
  total_units_sold: number;
  average_order_value_paise: number;
  orders_by_status: Record<string, number>;
  top_selling_products: RetailerAnalyticsProductItem[];
  in_stock_count: number;
  low_stock_count: number;
  out_of_stock_count: number;
}

// Basket Mission Types
export interface MissionItem {
  id: string;
  mission_id: string;
  product_id: string;
  variant_id: string;
  listing_id: string;
  retailer_id: string;
  product_name: string;
  brand: string;
  variant_name: string;
  sku: string;
  retailer_name: string;
  retailer_slug: string;
  image_url?: string | null;
  group_name: string;
  quantity: number;
  unit_price_paise: number;
  current_selling_price_paise: number;
  price_changed: boolean;
  available_stock: number;
  is_in_stock: boolean;
  subtotal_paise: number;
  is_selected: boolean;
  recommendation_reason: string;
  sort_order: number;
}

export interface MissionGroup {
  group_name: string;
  items: MissionItem[];
  subtotal_paise: number;
  items_count: number;
}

export interface MissionSummary {
  id: string;
  title: string;
  description?: string | null;
  budget_paise: number;
  total_cost_paise: number;
  remaining_budget_paise: number;
  is_over_budget: boolean;
  items_count: number;
  status: "ACTIVE" | "SAVED" | "COMPLETED" | "ARCHIVED";
  category_id?: string | null;
  category_name?: string | null;
  people_count: number;
  created_at: string;
  updated_at: string;
}

export interface MissionDetail {
  id: string;
  customer_id: string;
  title: string;
  description?: string | null;
  budget_paise: number;
  category_id?: string | null;
  category_name?: string | null;
  people_count: number;
  preferences: string[];
  excluded_brands: string[];
  status: "ACTIVE" | "SAVED" | "COMPLETED" | "ARCHIVED";
  total_cost_paise: number;
  remaining_budget_paise: number;
  is_over_budget: boolean;
  budget_shortfall_paise: number;
  items_count: number;
  unavailable_items_count: number;
  summary_explanation: string;
  groups: MissionGroup[];
  items: MissionItem[];
  created_at: string;
  updated_at: string;
}

export interface MissionCreatePayload {
  title: string;
  description?: string;
  budget_paise: number;
  category_id?: string;
  people_count?: number;
  preferences?: string[];
  excluded_brands?: string[];
}

export interface MissionUpdatePayload {
  title?: string;
  description?: string;
  budget_paise?: number;
  status?: "ACTIVE" | "SAVED" | "COMPLETED" | "ARCHIVED";
  people_count?: number;
  preferences?: string[];
  excluded_brands?: string[];
}

export interface MissionItemAddPayload {
  listing_id: string;
  quantity?: number;
  group_name?: string;
}

export interface MissionItemUpdatePayload {
  quantity?: number;
  is_selected?: boolean;
  group_name?: string;
}

export interface MissionItemReplacePayload {
  new_listing_id: string;
  quantity?: number;
}

export interface MissionAlternativeItem {
  listing_id: string;
  product_id: string;
  variant_id: string;
  product_name: string;
  brand: string;
  retailer_id: string;
  retailer_name: string;
  retailer_slug: string;
  selling_price_paise: number;
  price_diff_paise: number;
  available_stock: number;
  is_in_stock: boolean;
  image_url?: string | null;
  match_type: string;
}

export interface MissionAddToCartResponse {
  mission_id: string;
  added_items_count: number;
  skipped_items_count: number;
  warnings: string[];
  cart: unknown;
}

export interface MissionPreviewResponse {
  title: string;
  budget_paise: number;
  total_cost_paise: number;
  remaining_budget_paise: number;
  is_over_budget: boolean;
  budget_shortfall_paise: number;
  items_count: number;
  summary_explanation: string;
  groups: {
    group_name: string;
    items: unknown[];
    subtotal_paise: number;
    items_count: number;
  }[];
}

// ---------------------------------------------------------------------------
// Phase 2B: Substitute Intelligence
// ---------------------------------------------------------------------------

export type SubstituteType =
  | "CLOSEST_MATCH"
  | "BUDGET_FRIENDLY"
  | "BETTER_VALUE"
  | "PREMIUM_UPGRADE"
  | "AVAILABLE_NOW";

export type AvailabilityStatus = "IN_STOCK" | "LOW_STOCK" | "OUT_OF_STOCK";

export interface SpecComparison {
  attribute_key: string;
  label: string;
  original_value: unknown;
  substitute_value: unknown;
  is_match: boolean;
}

export interface SubstituteItem {
  listing_id: string;
  product_id: string;
  product_name: string;
  product_slug: string;
  brand: string;
  variant_id: string;
  variant_name: string;
  variant_sku: string;
  variant_attributes: Record<string, unknown>;
  primary_image_url?: string | null;
  retailer_id: string;
  retailer_name: string;
  retailer_slug: string;
  retailer_rating: number;
  retailer_verification_status: string;
  original_price_paise: number;
  selling_price_paise: number;
  price_diff_paise: number;
  price_diff_percentage: number;
  savings_percentage: number;
  available_stock: number;
  is_in_stock: boolean;
  availability_status: AvailabilityStatus;
  similarity_score: number;
  substitute_type: SubstituteType;
  applicable_types: SubstituteType[];
  reason: string;
  matching_specs: string[];
  differing_specs: string[];
  detailed_comparisons: SpecComparison[];
  compatibility_notes?: string | null;
}

export interface SubstituteListResponse {
  original_listing_id: string;
  original_product_name: string;
  original_product_slug: string;
  original_brand: string;
  original_category_id: string;
  original_category_name: string;
  original_selling_price_paise: number;
  original_is_in_stock: boolean;
  original_available_stock: number;
  original_attributes: Record<string, unknown>;
  substitutes: SubstituteItem[];
  total_count: number;
  trigger_reason?: string | null;
}

export interface CartItemReplaceRequest {
  new_listing_id: string;
  quantity?: number;
}

export interface CartItemReplaceResponse {
  cart: Cart;
  replaced_item_id: string;
  new_item_id: string;
  message: string;
}

// Phase 2C Basket Intent Memory types
export type ShoppingPriority =
  | "LOWEST_PRICE"
  | "QUALITY"
  | "DURABILITY"
  | "CONVENIENCE"
  | "BALANCED";

export type Frequency =
  | "WEEKLY"
  | "BIWEEKLY"
  | "MONTHLY"
  | "QUARTERLY"
  | "SEASONAL"
  | "CUSTOM";

export type MemoryType = "PREFERENCE" | "RECURRING_GOAL" | "NOTE" | "CONTEXT";
export type MemorySource =
  | "CUSTOMER_STATED"
  | "MISSION_DERIVED"
  | "SYSTEM_SUGGESTED";

export interface CustomerPreferenceProfile {
  id: string;
  customer_id: string;
  preferred_brands: string[];
  preferred_categories: string[];
  preferred_retailers: string[];
  preferred_price_range: {
    min_paise?: number;
    max_paise?: number;
    [key: string]: unknown;
  };
  preferred_attributes: Record<string, unknown>;
  shopping_priorities: (ShoppingPriority | string)[];
  category_preferences: Record<string, unknown>;
  personalization_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface CustomerPreferenceProfileRequest {
  preferred_brands?: string[];
  preferred_categories?: string[];
  preferred_retailers?: string[];
  preferred_price_range?: {
    min_paise?: number;
    max_paise?: number;
    [key: string]: unknown;
  };
  preferred_attributes?: Record<string, unknown>;
  shopping_priorities?: string[];
  category_preferences?: Record<string, unknown>;
  personalization_enabled?: boolean;
}

export interface PersonalizationConsentResponse {
  personalization_enabled: boolean;
  updated_at: string;
  message: string;
}

export interface RecurringIntention {
  id: string;
  customer_id: string;
  title: string;
  category_ids: string[];
  frequency: Frequency | string;
  budget_paise?: number | null;
  notes?: string | null;
  is_active: boolean;
  last_executed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface RecurringIntentionCreateRequest {
  title: string;
  category_ids?: string[];
  frequency?: string;
  budget_paise?: number | null;
  notes?: string | null;
}

export interface RecurringIntentionUpdateRequest {
  title?: string;
  category_ids?: string[];
  frequency?: string;
  budget_paise?: number | null;
  notes?: string | null;
  is_active?: boolean;
}

export interface IntentMemoryItem {
  id: string;
  customer_id: string;
  memory_type: MemoryType | string;
  key: string;
  value: Record<string, unknown> | string;
  summary: string;
  source: MemorySource | string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface IntentMemoryItemCreateRequest {
  memory_type?: string;
  key: string;
  value?: Record<string, unknown> | string;
  summary: string;
  source?: string;
}

export interface IntentOverviewResponse {
  profile?: CustomerPreferenceProfile | null;
  recurring_intentions: RecurringIntention[];
  memories: IntentMemoryItem[];
  active_intentions_count: number;
  total_memories_count: number;
  personalization_enabled: boolean;
}

export interface IntentSuggestionResponse {
  suggested_brands: string[];
  suggested_priorities: string[];
  suggested_budget_paise?: number | null;
  suggested_categories: string[];
  applicable_intentions: RecurringIntention[];
  personalization_enabled: boolean;
  explanation?: string | null;
}

// ================= Product Passport Types (Phase 2D) =================

export type ClaimReviewStatus = "PENDING" | "VERIFIED" | "REJECTED";
export type ClaimScope = "PRODUCT" | "LISTING";
export type ItemCondition = "NEW" | "REFURBISHED" | "OPEN_BOX" | "PRE_OWNED";

export interface PublicClaim {
  id: string;
  claim_scope: ClaimScope | string;
  claim_type: string;
  claim_key: string;
  claim_value: string;
  review_status: ClaimReviewStatus | string;
  is_public_evidence: boolean;
  evidence_url?: string | null;
  evidence_type?: string | null;
  created_at: string;
  reviewed_at?: string | null;
}

export interface PublicListingPassport {
  id: string;
  listing_id: string;
  retailer_id: string;
  retailer_name: string;
  item_condition: ItemCondition | string;
  seller_warranty?: string | null;
  packaging_notes?: string | null;
  fulfillment_notes?: string | null;
  claims: PublicClaim[];
  created_at: string;
  updated_at: string;
}

export interface ListingBrief {
  listing_id: string;
  retailer_id: string;
  retailer_name: string;
  selling_price_paise: number;
  is_in_stock: boolean;
  item_condition: string;
}

export interface PublicProductPassport {
  id?: string | null;
  product_id: string;
  product_name: string;
  brand: string;
  category_name: string;
  manufacturer?: string | null;
  country_of_origin?: string | null;
  model_number?: string | null;
  gtin_ean_upc?: string | null;
  materials: unknown[];
  technical_specs: Record<string, unknown>;
  package_contents: string[];
  usage_instructions?: string | null;
  safety_instructions?: string | null;
  warranty_info?: string | null;
  certifications: unknown[];
  claims: PublicClaim[];
  listing_passport?: PublicListingPassport | null;
  available_listings: ListingBrief[];
  created_at?: string | null;
  updated_at?: string | null;
}

export interface RetailerClaim {
  id: string;
  passport_id?: string | null;
  listing_id?: string | null;
  retailer_id?: string | null;
  claim_scope: string;
  claim_type: string;
  claim_key: string;
  claim_value: string;
  evidence_url?: string | null;
  evidence_type: string;
  evidence_notes?: string | null;
  is_public_evidence: boolean;
  review_status: ClaimReviewStatus | string;
  rejection_reason?: string | null;
  submitted_by_user_id?: string | null;
  reviewed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface RetailerListingPassportDetail {
  id: string;
  listing_id: string;
  retailer_id: string;
  item_condition: ItemCondition | string;
  seller_warranty?: string | null;
  packaging_notes?: string | null;
  fulfillment_notes?: string | null;
  claims: RetailerClaim[];
  created_at: string;
  updated_at: string;
}

export interface RetailerListingPassportUpsertRequest {
  item_condition?: ItemCondition | string;
  seller_warranty?: string | null;
  packaging_notes?: string | null;
  fulfillment_notes?: string | null;
}

export interface RetailerClaimCreateRequest {
  claim_scope?: ClaimScope | string;
  claim_type: string;
  claim_key: string;
  claim_value: string;
  evidence_url?: string | null;
  evidence_type?: string;
  evidence_notes?: string | null;
  is_public_evidence?: boolean;
}

export interface RetailerClaimUpdateRequest {
  claim_type?: string;
  claim_key?: string;
  claim_value?: string;
  evidence_url?: string | null;
  evidence_type?: string;
  evidence_notes?: string | null;
  is_public_evidence?: boolean;
}

export interface AdminClaim {
  id: string;
  passport_id?: string | null;
  listing_id?: string | null;
  retailer_id?: string | null;
  retailer_name?: string | null;
  product_id?: string | null;
  product_name?: string | null;
  claim_scope: string;
  claim_type: string;
  claim_key: string;
  claim_value: string;
  evidence_url?: string | null;
  evidence_type: string;
  evidence_notes?: string | null;
  is_public_evidence: boolean;
  review_status: ClaimReviewStatus | string;
  rejection_reason?: string | null;
  submitted_by_user_id?: string | null;
  reviewed_by_user_id?: string | null;
  reviewed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AdminClaimQueueResponse {
  items: AdminClaim[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface AdminProductPassportUpsertRequest {
  manufacturer?: string | null;
  country_of_origin?: string | null;
  model_number?: string | null;
  gtin_ean_upc?: string | null;
  materials?: unknown[];
  technical_specs?: Record<string, unknown>;
  package_contents?: string[];
  usage_instructions?: string | null;
  safety_instructions?: string | null;
  warranty_info?: string | null;
  certifications?: unknown[];
}



