import { apiClient } from "@/lib/api/client";
import type { RetailerListingItem } from "@/types";

export async function loadMyListings(): Promise<RetailerListingItem[]> {
  const r = await apiClient.listRetailerListings({ is_active: true, limit: 100 });
  return r.items;
}
