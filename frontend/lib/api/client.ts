import type {
  Address,
  AddressCreatePayload,
  AddressUpdatePayload,
  ApiErrorEnvelope,
  ApiInfoResponse,
  AuthResponse,
  Cart,
  CartItem,
  CartMergeResponse,
  Category,
  HealthResponse,
  MessageResponse,
  ProductDetail,
  ProductFilterParams,
  ProductListResponse,
  ReadyResponse,
  Retailer,
  TokenResponse,
  User,
  Quote,
  QuoteCreatePayload,
  QuoteValidationResult,
  Reservation,
  ReservationCreatePayload,
  ReservationReleaseResponse,
  Order,
  CreateOrderRequest,
  OrderListResponse,
  OrderCancellationResponse,
  OrderTrackingResponse,
  ReturnCreateRequest,
  OrderReturn,
  NotificationListResponse,
  PaymentInitiateResponse,
  PaymentVerifyRequest,
  PaymentVerifyResponse,
  PaymentRefundRequest,
  PaymentRefundResponse,
  SearchFilterParams,
  SearchResponse,
  SuggestionsResponse,
  AdminOverview,
  AdminRetailerListItem,
  RetailerOverview,
  RetailerProfile,
  RetailerRegisterPayload,
} from "@/types";

export class ApiClientError extends Error {
  public readonly code: string;
  public readonly status: number;
  public readonly requestId?: string;
  public readonly details: unknown[];

  constructor(
    message: string,
    status: number,
    code = "UNKNOWN_ERROR",
    requestId?: string,
    details: unknown[] = []
  ) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    this.details = details;
  }
}

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(^|;\\s*)(${name})=([^;]*)`));
  return match ? decodeURIComponent(match[3]) : null;
}

class ApiClient {
  private readonly baseUrl: string;
  private refreshPromise: Promise<TokenResponse | null> | null = null;

  constructor() {
    this.baseUrl =
      process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") ||
      "http://localhost:8000";
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
    isRetry = false
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;
    const method = (options.method || "GET").toUpperCase();

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(options.headers as Record<string, string>),
    };

    // Attach CSRF token on state-mutating browser requests if not already set
    if (["POST", "PATCH", "PUT", "DELETE"].includes(method) && !headers["X-CSRF-Token"]) {
      const csrfToken = getCookie("XSRF-TOKEN");
      if (csrfToken) {
        headers["X-CSRF-Token"] = csrfToken;
      }
    }

    try {
      const response = await fetch(url, {
        credentials: "include",
        ...options,
        headers,
      });

      if (!response.ok) {
        // Attempt single-flight token refresh on 401 (if not already retried and not an auth route)
        const isAuthRoute =
          endpoint.includes("/auth/login") ||
          endpoint.includes("/auth/register") ||
          endpoint.includes("/auth/refresh");

        if (response.status === 401 && !isRetry && !isAuthRoute) {
          const refreshed = await this.executeTokenRefresh();
          if (refreshed) {
            return this.request<T>(endpoint, options, true);
          }
        }

        let errorData: ApiErrorEnvelope | null = null;
        try {
          const errorText = await response.text();
          if (errorText && errorText.trim()) {
            errorData = JSON.parse(errorText) as ApiErrorEnvelope;
          }
        } catch {
          // Response body was not JSON
        }

        const code = errorData?.error?.code || `HTTP_${response.status}`;
        let message =
          errorData?.error?.message ||
          `API request failed with status ${response.status}`;
        const requestId =
          errorData?.error?.request_id ||
          response.headers.get("x-request-id") ||
          undefined;
        const details = errorData?.error?.details || [];

        // If backend returned generic validation message and details array contains field errors, enrich message
        if (
          code === "VALIDATION_ERROR" &&
          Array.isArray(details) &&
          details.length > 0 &&
          message === "The request payload validation failed."
        ) {
          const detailMsgs = (details as Array<{ loc?: (string | number)[]; msg?: string }>)
            .map((d) => {
              const field = d.loc?.filter((x) => x !== "body").join(".") || "field";
              return `${field}: ${d.msg || "invalid value"}`;
            })
            .filter(Boolean);
          if (detailMsgs.length > 0) {
            message = `The request payload validation failed: ${detailMsgs.join("; ")}`;
          }
        }

        throw new ApiClientError(
          message,
          response.status,
          code,
          requestId,
          details
        );
      }

      if (response.status === 204) {
        return undefined as T;
      }

      const text = await response.text();
      if (!text || text.trim() === "") {
        return undefined as T;
      }

      return JSON.parse(text) as T;
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        throw err;
      }
      const message =
        err instanceof Error ? err.message : "Network error or server unreachable";
      throw new ApiClientError(message, 0, "NETWORK_ERROR");
    }
  }

  /**
   * Concurrency-safe token refresh avoiding duplicate simultaneous requests.
   */
  private async executeTokenRefresh(): Promise<TokenResponse | null> {
    if (!this.refreshPromise) {
      this.refreshPromise = this.post<TokenResponse>("/api/v1/auth/refresh")
        .catch(() => null)
        .finally(() => {
          this.refreshPromise = null;
        });
    }
    return this.refreshPromise;
  }

  public async get<T>(endpoint: string, options?: RequestInit): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: "GET" });
  }

  public async post<T>(
    endpoint: string,
    body?: unknown,
    options?: RequestInit
  ): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: "POST",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  }

  public async put<T>(
    endpoint: string,
    body?: unknown,
    options?: RequestInit
  ): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: "PUT",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  }

  public async patch<T>(
    endpoint: string,
    body?: unknown,
    options?: RequestInit
  ): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: "PATCH",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  }

  public async delete<T = void>(
    endpoint: string,
    body?: unknown,
    options?: RequestInit
  ): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: "DELETE",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  }

  // Baseline system health endpoints
  public async getHealth(): Promise<HealthResponse> {
    return this.get<HealthResponse>("/health");
  }

  public async getReady(): Promise<ReadyResponse> {
    return this.get<ReadyResponse>("/ready");
  }

  public async getInfo(): Promise<ApiInfoResponse> {
    return this.get<ApiInfoResponse>("/api/v1/info");
  }

  // Catalogue endpoints
  public async getCategories(): Promise<Category[]> {
    return this.get<Category[]>("/api/v1/categories");
  }

  public async getRetailers(): Promise<Retailer[]> {
    return this.get<Retailer[]>("/api/v1/retailers");
  }

  public async getProducts(
    params: ProductFilterParams = {}
  ): Promise<ProductListResponse> {
    const searchParams = new URLSearchParams();
    if (params.category_slug) searchParams.set("category_slug", params.category_slug);
    if (params.category_id) searchParams.set("category_id", params.category_id);
    if (params.retailer_id) searchParams.set("retailer_id", params.retailer_id);
    if (params.brand) searchParams.set("brand", params.brand);
    if (params.search) searchParams.set("search", params.search);
    if (params.min_price !== undefined)
      searchParams.set("min_price", params.min_price.toString());
    if (params.max_price !== undefined)
      searchParams.set("max_price", params.max_price.toString());
    if (params.in_stock !== undefined)
      searchParams.set("in_stock", params.in_stock.toString());
    if (params.sort_by) searchParams.set("sort_by", params.sort_by);
    if (params.page) searchParams.set("page", params.page.toString());
    if (params.limit) searchParams.set("limit", params.limit.toString());

    const qs = searchParams.toString();
    return this.get<ProductListResponse>(`/api/v1/products${qs ? `?${qs}` : ""}`);
  }

  public async getProduct(idOrSlug: string): Promise<ProductDetail> {
    return this.get<ProductDetail>(`/api/v1/products/${encodeURIComponent(idOrSlug)}`);
  }

  // ================= Identity & Authentication =================
  public async register(payload: {
    email: string;
    password: string;
    full_name: string;
    phone?: string | null;
  }): Promise<AuthResponse> {
    return this.post<AuthResponse>("/api/v1/auth/register", payload);
  }

  public async registerRetailer(
    payload: RetailerRegisterPayload
  ): Promise<AuthResponse> {
    return this.post<AuthResponse>("/api/v1/auth/retailer/register", payload);
  }

  public async login(payload: {
    email: string;
    password: string;
  }): Promise<AuthResponse> {
    return this.post<AuthResponse>("/api/v1/auth/login", payload);
  }

  public async refreshToken(): Promise<TokenResponse> {
    return this.post<TokenResponse>("/api/v1/auth/refresh");
  }

  public async logout(): Promise<MessageResponse> {
    return this.post<MessageResponse>("/api/v1/auth/logout");
  }

  public async logoutAll(): Promise<MessageResponse> {
    return this.post<MessageResponse>("/api/v1/auth/logout-all");
  }

  public async getProfile(): Promise<User> {
    return this.get<User>("/api/v1/users/me");
  }

  // ================= Address Management =================
  public async getAddresses(): Promise<Address[]> {
    return this.get<Address[]>("/api/v1/addresses");
  }

  public async createAddress(payload: AddressCreatePayload): Promise<Address> {
    return this.post<Address>("/api/v1/addresses", payload);
  }

  public async updateAddress(
    id: string,
    payload: AddressUpdatePayload
  ): Promise<Address> {
    return this.patch<Address>(`/api/v1/addresses/${encodeURIComponent(id)}`, payload);
  }

  public async deleteAddress(id: string): Promise<MessageResponse> {
    return this.delete<MessageResponse>(`/api/v1/addresses/${encodeURIComponent(id)}`);
  }

  // ================= Cart Management =================
  public async getCart(): Promise<Cart> {
    return this.get<Cart>("/api/v1/cart");
  }

  public async addToCart(listingId: string, quantity = 1): Promise<Cart> {
    return this.post<Cart>("/api/v1/cart/items", {
      listing_id: listingId,
      quantity,
    });
  }

  public async updateCartItemQuantity(
    itemId: string,
    quantity: number
  ): Promise<Cart> {
    return this.patch<Cart>(`/api/v1/cart/items/${encodeURIComponent(itemId)}`, {
      quantity,
    });
  }

  public async removeCartItem(itemId: string): Promise<Cart> {
    return this.delete<Cart>(`/api/v1/cart/items/${encodeURIComponent(itemId)}`);
  }

  public async clearCart(): Promise<Cart> {
    return this.delete<Cart>("/api/v1/cart");
  }

  public async mergeCart(guestToken?: string): Promise<CartMergeResponse> {
    return this.post<CartMergeResponse>("/api/v1/cart/merge", {
      guest_token: guestToken,
    });
  }

  // ================= Quotes & Pricing (Phase 2C) =================
  public async createQuote(payload: QuoteCreatePayload = {}): Promise<Quote> {
    return this.post<Quote>("/api/v1/quotes", payload);
  }

  public async getQuote(quoteId: string): Promise<Quote> {
    return this.get<Quote>(`/api/v1/quotes/${encodeURIComponent(quoteId)}`);
  }

  public async validateQuote(quoteId: string): Promise<QuoteValidationResult> {
    return this.post<QuoteValidationResult>(
      `/api/v1/quotes/${encodeURIComponent(quoteId)}/validate`,
      {}
    );
  }

  public async refreshQuote(quoteId: string): Promise<Quote> {
    return this.post<Quote>(
      `/api/v1/quotes/${encodeURIComponent(quoteId)}/refresh`,
      {}
    );
  }

  public async listQuotes(): Promise<Quote[]> {
    return this.get<Quote[]>("/api/v1/quotes");
  }

  // Phase 2D: Inventory Reservations
  public async createReservation(
    payload: ReservationCreatePayload,
    idempotencyKey?: string,
  ): Promise<Reservation> {
    const headers: Record<string, string> = {};
    if (idempotencyKey) {
      headers["Idempotency-Key"] = idempotencyKey;
    }
    return this.post<Reservation>("/api/v1/reservations", payload, { headers });
  }

  public async getReservation(reservationId: string): Promise<Reservation> {
    return this.get<Reservation>(
      `/api/v1/reservations/${encodeURIComponent(reservationId)}`,
    );
  }

  public async releaseReservation(
    reservationId: string,
  ): Promise<ReservationReleaseResponse> {
    return this.post<ReservationReleaseResponse>(
      `/api/v1/reservations/${encodeURIComponent(reservationId)}/release`,
      {},
    );
  }

  // ================= Orders & Checkout (Phase 2E) =================
  public async createOrder(
    payload: CreateOrderRequest,
    idempotencyKey?: string,
  ): Promise<Order> {
    const headers: Record<string, string> = {};
    if (idempotencyKey) {
      headers["Idempotency-Key"] = idempotencyKey;
    }
    return this.post<Order>("/api/v1/orders", payload, { headers });
  }

  public async getOrder(orderId: string, accessToken?: string): Promise<Order> {
    const query = accessToken ? `?access_token=${encodeURIComponent(accessToken)}` : "";
    return this.get<Order>(`/api/v1/orders/${encodeURIComponent(orderId)}${query}`);
  }

  public async guestLookupOrder(orderNumber: string, accessToken: string): Promise<Order> {
    return this.post<Order>("/api/v1/orders/guest-lookup", {
      order_number: orderNumber,
      access_token: accessToken,
    });
  }

  public async listOrders(
    limit = 20,
    offset = 0,
    status?: string,
    search?: string,
    fromDate?: string,
    toDate?: string,
  ): Promise<OrderListResponse> {
    const params = new URLSearchParams({
      limit: String(limit),
      offset: String(offset),
    });
    if (status) params.set("status", status);
    if (search) params.set("search", search);
    if (fromDate) params.set("from_date", fromDate);
    if (toDate) params.set("to_date", toDate);
    const res = await this.get<OrderListResponse>(`/api/v1/orders?${params.toString()}`);
    const items = res.items || res.orders || [];
    return {
      total: res.total ?? items.length,
      items,
      orders: res.orders || items,
    };
  }

  public async cancelOrder(
    orderId: string,
    reason: string,
    idempotencyKey?: string,
    accessToken?: string,
  ): Promise<OrderCancellationResponse> {
    const headers: Record<string, string> = {};
    if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;
    if (accessToken) headers["X-Guest-Access-Token"] = accessToken;
    return this.post<OrderCancellationResponse>(
      `/api/v1/orders/${encodeURIComponent(orderId)}/cancel`,
      { reason },
      { headers },
    );
  }

  public async getOrderTracking(
    orderId: string,
    accessToken?: string,
  ): Promise<OrderTrackingResponse> {
    const query = accessToken ? `?access_token=${encodeURIComponent(accessToken)}` : "";
    return this.get<OrderTrackingResponse>(
      `/api/v1/orders/${encodeURIComponent(orderId)}/tracking${query}`,
    );
  }

  public async requestReturn(
    orderId: string,
    payload: ReturnCreateRequest,
    idempotencyKey?: string,
    accessToken?: string,
  ): Promise<OrderReturn> {
    const headers: Record<string, string> = {};
    if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;
    if (accessToken) headers["X-Guest-Access-Token"] = accessToken;
    return this.post<OrderReturn>(
      `/api/v1/orders/${encodeURIComponent(orderId)}/returns`,
      payload,
      { headers },
    );
  }

  public async listOrderReturns(
    orderId: string,
    accessToken?: string,
  ): Promise<OrderReturn[]> {
    const query = accessToken ? `?access_token=${encodeURIComponent(accessToken)}` : "";
    return this.get<OrderReturn[]>(
      `/api/v1/orders/${encodeURIComponent(orderId)}/returns${query}`,
    );
  }

  public async listNotifications(
    limit = 50,
    offset = 0,
  ): Promise<NotificationListResponse> {
    return this.get<NotificationListResponse>(
      `/api/v1/notifications?limit=${encodeURIComponent(limit)}&skip=${encodeURIComponent(offset)}`,
    );
  }

  public async getUnreadNotificationCount(): Promise<{ unread_count: number }> {
    return this.get<{ unread_count: number }>("/api/v1/notifications/unread-count");
  }

  public async markNotificationAsRead(
    notificationId: string,
  ): Promise<{ success: boolean }> {
    return this.post<{ success: boolean }>(
      `/api/v1/notifications/${encodeURIComponent(notificationId)}/read`,
      {},
    );
  }

  // ================= Payments & Refunds (Phase 2F) =================
  public async initiatePayment(
    orderId: string,
    idempotencyKey?: string,
  ): Promise<PaymentInitiateResponse> {
    const headers: Record<string, string> = {};
    if (idempotencyKey) {
      headers["Idempotency-Key"] = idempotencyKey;
    }
    return this.post<PaymentInitiateResponse>(
      `/api/v1/orders/${encodeURIComponent(orderId)}/payments`,
      {},
      { headers },
    );
  }

  public async verifyPayment(
    orderId: string,
    payload: PaymentVerifyRequest,
  ): Promise<PaymentVerifyResponse> {
    return this.post<PaymentVerifyResponse>(
      `/api/v1/orders/${encodeURIComponent(orderId)}/payments/verify`,
      payload,
    );
  }

  public async requestRefund(
    orderId: string,
    payload: PaymentRefundRequest,
    idempotencyKey?: string,
  ): Promise<PaymentRefundResponse> {
    const headers: Record<string, string> = {};
    if (idempotencyKey) {
      headers["Idempotency-Key"] = idempotencyKey;
    }
    return this.post<PaymentRefundResponse>(
      `/api/v1/orders/${encodeURIComponent(orderId)}/refunds`,
      payload,
      { headers },
    );
  }

  // Universal Search Methods (Phase 3E)
  public async searchProducts(
    params: SearchFilterParams = {},
  ): Promise<SearchResponse> {
    const query = new URLSearchParams();
    if (params.q) query.set("q", params.q);
    if (params.category) query.set("category", params.category);
    if (params.brand) query.set("brand", params.brand);
    if (params.retailer_id) query.set("retailer_id", params.retailer_id);
    if (params.min_price !== undefined) query.set("min_price", String(params.min_price));
    if (params.max_price !== undefined) query.set("max_price", String(params.max_price));
    if (params.in_stock !== undefined) query.set("in_stock", String(params.in_stock));
    if (params.sort) query.set("sort", params.sort);
    if (params.page !== undefined) query.set("page", String(params.page));
    if (params.page_size !== undefined) query.set("page_size", String(params.page_size));
    if (params.force_fallback) query.set("force_fallback", "true");

    const qs = query.toString();
    const endpoint = qs ? `/api/v1/search?${qs}` : "/api/v1/search";
    return this.get<SearchResponse>(endpoint);
  }

  public async getSearchSuggestions(
    query: string,
    limit: number = 5,
  ): Promise<SuggestionsResponse> {
    const qs = new URLSearchParams({ q: query, limit: String(limit) }).toString();
    return this.get<SuggestionsResponse>(`/api/v1/search/suggestions?${qs}`);
  }

  // ================= Retailer Portal Methods (Phase 5A) =================
  public async getRetailerProfile(): Promise<RetailerProfile> {
    return this.get<RetailerProfile>("/api/v1/retailer/profile");
  }

  public async updateRetailerProfile(
    payload: Partial<RetailerProfile>
  ): Promise<RetailerProfile> {
    return this.put<RetailerProfile>("/api/v1/retailer/profile", payload);
  }

  public async getRetailerOverview(): Promise<RetailerOverview> {
    return this.get<RetailerOverview>("/api/v1/retailer/overview");
  }

  // ================= Admin Portal Methods (Phase 5A) =================
  public async getAdminOverview(): Promise<AdminOverview> {
    return this.get<AdminOverview>("/api/v1/admin/overview");
  }

  public async listAdminRetailers(
    status?: string
  ): Promise<AdminRetailerListItem[]> {
    const endpoint = status
      ? `/api/v1/admin/retailers?status=${encodeURIComponent(status)}`
      : "/api/v1/admin/retailers";
    return this.get<AdminRetailerListItem[]>(endpoint);
  }

  public async verifyRetailer(
    retailerId: string,
    status: string,
    rejectionReason?: string
  ): Promise<AdminRetailerListItem> {
    return this.post<AdminRetailerListItem>(
      `/api/v1/admin/retailers/${encodeURIComponent(retailerId)}/verify`,
      { status, rejection_reason: rejectionReason }
    );
  }
}

export const apiClient = new ApiClient();
