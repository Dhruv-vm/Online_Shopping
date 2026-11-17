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
        const message =
          errorData?.error?.message ||
          `API request failed with status ${response.status}`;
        const requestId =
          errorData?.error?.request_id ||
          response.headers.get("x-request-id") ||
          undefined;
        const details = errorData?.error?.details || [];

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
}

export const apiClient = new ApiClient();
