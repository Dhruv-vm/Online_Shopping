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
  role: string;
  is_active: boolean;
  created_at: string;
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

// Phase 2E: Orders, Checkout Orchestration & Transactional Outbox
export type OrderStatus =
  | "PENDING_PAYMENT"
  | "CONFIRMED"
  | "PROCESSING"
  | "SHIPPED"
  | "DELIVERED"
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

export interface Order {
  id: string;
  order_number: string;
  customer_id?: string | null;
  is_guest: boolean;
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
  fulfilling_capture_id?: string | null;
  payment_window_expires_at?: string | null;
  items: OrderItem[];
  status_history?: OrderStatusHistoryEntry[];
  created_at: string;
  updated_at: string;
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
  orders: Order[];
  total: number;
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
