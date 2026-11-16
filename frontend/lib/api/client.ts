import type {
  ApiErrorEnvelope,
  ApiInfoResponse,
  HealthResponse,
  ReadyResponse,
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

class ApiClient {
  private readonly baseUrl: string;

  constructor() {
    this.baseUrl =
      process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") ||
      "http://localhost:8000";
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(options.headers as Record<string, string>),
    };

    try {
      const response = await fetch(url, {
        ...options,
        headers,
      });

      if (!response.ok) {
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
}

export const apiClient = new ApiClient();
