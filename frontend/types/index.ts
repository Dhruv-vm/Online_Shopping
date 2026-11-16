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
