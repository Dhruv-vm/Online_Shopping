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
