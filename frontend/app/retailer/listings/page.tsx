"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  Layers,
  PlusCircle,
  Search,
  Filter,
  RefreshCw,
  Edit,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  X,
  Boxes,
  FileCheck2,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiClient } from "@/lib/api/client";
import type { RetailerListingItem, RetailerListingUpdatePayload } from "@/types";

export default function RetailerListingsPage() {
  const [listings, setListings] = useState<RetailerListingItem[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"ALL" | "ACTIVE" | "LOW_STOCK">("ALL");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Edit Pricing Modal State
  const [editingListing, setEditingListing] = useState<RetailerListingItem | null>(null);
  const [editSellingPrice, setEditSellingPrice] = useState("");
  const [editOriginalPrice, setEditOriginalPrice] = useState("");
  const [editSellerSku, setEditSellerSku] = useState("");
  const [editActive, setEditActive] = useState(true);
  const [isSavingEdit, setIsSavingEdit] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  const loadListings = useCallback(async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const data = await apiClient.listRetailerListings({
        search: searchQuery.trim() || undefined,
        is_active: statusFilter === "ACTIVE" ? true : undefined,
        is_low_stock: statusFilter === "LOW_STOCK" ? true : undefined,
      });
      setListings(data.items);
      setTotal(data.total);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to load store listings.");
    } finally {
      setIsLoading(false);
    }
  }, [searchQuery, statusFilter]);

  useEffect(() => {
    loadListings();
  }, [loadListings]);

  const openEditModal = (item: RetailerListingItem) => {
    setEditingListing(item);
    setEditSellingPrice((item.selling_price_paise / 100).toFixed(2));
    setEditOriginalPrice((item.original_price_paise / 100).toFixed(2));
    setEditSellerSku(item.seller_sku || "");
    setEditActive(item.is_active);
    setModalError(null);
  };

  const closeEditModal = () => {
    setEditingListing(null);
    setModalError(null);
  };

  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingListing) return;

    const sellingRupees = parseFloat(editSellingPrice);
    const originalRupees = parseFloat(editOriginalPrice);

    if (isNaN(sellingRupees) || sellingRupees < 0) {
      setModalError("Please enter a valid positive selling price.");
      return;
    }
    if (isNaN(originalRupees) || originalRupees < 0) {
      setModalError("Please enter a valid positive MRP.");
      return;
    }
    if (sellingRupees > originalRupees) {
      setModalError("Selling price cannot exceed the original MRP price.");
      return;
    }

    setIsSavingEdit(true);
    setModalError(null);
    try {
      const payload: RetailerListingUpdatePayload = {
        selling_price_paise: Math.round(sellingRupees * 100),
        original_price_paise: Math.round(originalRupees * 100),
        seller_sku: editSellerSku.trim() || null,
        is_active: editActive,
      };

      const updated = await apiClient.updateRetailerListing(editingListing.id, payload);
      setListings((prev) =>
        prev.map((item) => (item.id === updated.id ? updated : item))
      );
      setSuccessMsg(`Successfully updated pricing for "${updated.product_name}".`);
      closeEditModal();
    } catch (err: unknown) {
      setModalError(err instanceof Error ? err.message : "Failed to update listing.");
    } finally {
      setIsSavingEdit(false);
    }
  };

  const handleToggleActive = async (item: RetailerListingItem) => {
    try {
      const updated = await apiClient.updateRetailerListing(item.id, {
        is_active: !item.is_active,
      });
      setListings((prev) =>
        prev.map((curr) => (curr.id === updated.id ? updated : curr))
      );
      setSuccessMsg(
        `Listing "${item.product_name}" is now ${
          updated.is_active ? "ACTIVE" : "PAUSED"
        }.`
      );
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to toggle listing status.");
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Action Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Layers className="h-6 w-6 text-blue-600" />
            Store Product Listings
          </h1>
          <p className="text-sm text-muted-foreground">
            Manage your store catalogue pricing, active marketplace status, and SKU inventory.
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <Button
            variant="outline"
            size="sm"
            onClick={loadListings}
            disabled={isLoading}
            className="gap-2"
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </Button>

          <Link href="/retailer/listings/new">
            <Button size="sm" className="bg-blue-600 hover:bg-blue-700 text-white gap-2 shadow-xs">
              <PlusCircle className="h-4 w-4" />
              Add Product to Store
            </Button>
          </Link>
        </div>
      </div>

      {/* Messages */}
      {errorMsg && (
        <div className="p-3.5 rounded-lg border border-red-500/30 bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 text-sm flex items-center gap-2">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}
      {successMsg && (
        <div className="p-3.5 rounded-lg border border-emerald-500/30 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 text-sm flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 shrink-0" />
            <span>{successMsg}</span>
          </div>
          <button onClick={() => setSuccessMsg(null)} className="text-xs hover:opacity-75">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* Filters & Search */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search by product name, variant, or SKU..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9 text-sm"
          />
        </div>

        <div className="flex items-center gap-1.5 border rounded-lg p-1 bg-card shrink-0">
          <button
            onClick={() => setStatusFilter("ALL")}
            className={`px-3 py-1 text-xs rounded-md font-medium transition-colors ${
              statusFilter === "ALL"
                ? "bg-blue-600 text-white"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            All ({total})
          </button>
          <button
            onClick={() => setStatusFilter("ACTIVE")}
            className={`px-3 py-1 text-xs rounded-md font-medium transition-colors ${
              statusFilter === "ACTIVE"
                ? "bg-blue-600 text-white"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            Active Only
          </button>
          <button
            onClick={() => setStatusFilter("LOW_STOCK")}
            className={`px-3 py-1 text-xs rounded-md font-medium transition-colors ${
              statusFilter === "LOW_STOCK"
                ? "bg-amber-600 text-white"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            Low Stock Alerts
          </button>
        </div>
      </div>

      {/* Listings Table Card */}
      <div className="rounded-xl border bg-card shadow-xs overflow-hidden">
        {isLoading ? (
          <div className="p-12 text-center text-muted-foreground">
            <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-solid border-blue-600 border-r-transparent align-[-0.125em] mb-2" />
            <p className="text-sm">Loading store product listings...</p>
          </div>
        ) : listings.length === 0 ? (
          <div className="p-12 text-center space-y-4">
            <div className="inline-flex h-12 w-12 items-center justify-center rounded-xl bg-blue-50 text-blue-600 dark:bg-blue-950/50">
              <Layers className="h-6 w-6" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-foreground">No Listings Found</h3>
              <p className="text-xs text-muted-foreground mt-1 max-w-sm mx-auto">
                {searchQuery || statusFilter !== "ALL"
                  ? "No listings match your search or status filter. Try clearing your query."
                  : "Your store catalogue is empty. Select products from the platform catalogue to publish your first listing."}
              </p>
            </div>
            <Link href="/retailer/listings/new">
              <Button size="sm" className="bg-blue-600 hover:bg-blue-700 text-white gap-2">
                <PlusCircle className="h-4 w-4" />
                Add Your First Product
              </Button>
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-muted/50 border-b text-muted-foreground uppercase text-[10px] tracking-wider">
                <tr>
                  <th className="py-3 px-4 font-semibold">Product & Variant</th>
                  <th className="py-3 px-4 font-semibold">SKU / Seller SKU</th>
                  <th className="py-3 px-4 font-semibold text-right">MRP (Paise)</th>
                  <th className="py-3 px-4 font-semibold text-right">Selling Price</th>
                  <th className="py-3 px-4 font-semibold text-center">Available Stock</th>
                  <th className="py-3 px-4 font-semibold text-center">Status</th>
                  <th className="py-3 px-4 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {listings.map((item) => {
                  const inv = item.inventory;
                  return (
                    <tr key={item.id} className="hover:bg-muted/30 transition-colors">
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-3">
                          {item.image_url ? (
                            <img
                              src={item.image_url}
                              alt={item.product_name}
                              className="h-10 w-10 rounded-md object-cover border bg-muted shrink-0"
                            />
                          ) : (
                            <div className="h-10 w-10 rounded-md bg-muted flex items-center justify-center text-muted-foreground shrink-0">
                              <Layers className="h-5 w-5" />
                            </div>
                          )}
                          <div>
                            <div className="font-semibold text-foreground text-sm line-clamp-1">
                              {item.product_name}
                            </div>
                            <div className="text-[11px] text-muted-foreground line-clamp-1">
                              {item.variant_name} • <span className="font-medium text-foreground">{item.brand}</span>
                            </div>
                          </div>
                        </div>
                      </td>

                      <td className="py-3 px-4 font-mono text-[11px]">
                        <div>{item.variant_sku}</div>
                        {item.seller_sku && (
                          <div className="text-[10px] text-muted-foreground">
                            Store: {item.seller_sku}
                          </div>
                        )}
                      </td>

                      <td className="py-3 px-4 text-right line-through text-muted-foreground font-mono">
                        ₹{(item.original_price_paise / 100).toFixed(2)}
                      </td>

                      <td className="py-3 px-4 text-right font-semibold text-foreground font-mono text-sm">
                        ₹{(item.selling_price_paise / 100).toFixed(2)}
                      </td>

                      <td className="py-3 px-4 text-center">
                        <div className="inline-flex flex-col items-center">
                          <span
                            className={`font-mono font-bold text-xs ${
                              inv.is_out_of_stock
                                ? "text-red-600 dark:text-red-400"
                                : inv.is_low_stock
                                ? "text-amber-600 dark:text-amber-400"
                                : "text-emerald-600 dark:text-emerald-400"
                            }`}
                          >
                            {inv.available_quantity}
                          </span>
                          {inv.is_out_of_stock ? (
                            <Badge variant="outline" className="text-[9px] px-1 py-0 border-red-500/40 text-red-600 bg-red-50/50">
                              Out of Stock
                            </Badge>
                          ) : inv.is_low_stock ? (
                            <Badge variant="outline" className="text-[9px] px-1 py-0 border-amber-500/40 text-amber-700 bg-amber-50/50">
                              Low Stock
                            </Badge>
                          ) : (
                            <span className="text-[10px] text-muted-foreground font-mono">
                              (Holds: {inv.reserved_quantity})
                            </span>
                          )}
                        </div>
                      </td>

                      <td className="py-3 px-4 text-center">
                        <button
                          onClick={() => handleToggleActive(item)}
                          className="cursor-pointer"
                          title="Click to toggle active status"
                        >
                          {item.is_active ? (
                            <Badge className="bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border-0 hover:bg-emerald-200">
                              Active
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="text-zinc-500 border-zinc-300 hover:bg-zinc-100">
                              Paused
                            </Badge>
                          )}
                        </button>
                      </td>

                      <td className="py-3 px-4 text-right space-x-2">
                        <Link href={`/retailer/listings/${item.id}/passport`}>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-8 w-8 p-0"
                            title="Product Passport & Claims"
                          >
                            <FileCheck2 className="h-4 w-4 text-emerald-600" />
                          </Button>
                        </Link>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openEditModal(item)}
                          className="h-8 w-8 p-0"
                          title="Edit Pricing & SKU"
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Link href={`/retailer/inventory?search=${encodeURIComponent(item.variant_sku)}`}>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-8 w-8 p-0 text-emerald-600 hover:text-emerald-700"
                            title="Manage Stock"
                          >
                            <Boxes className="h-4 w-4" />
                          </Button>
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Edit Pricing Modal */}
      {editingListing && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-card border rounded-2xl max-w-md w-full p-6 shadow-xl space-y-4 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between border-b pb-3">
              <div>
                <h3 className="font-bold text-foreground text-base">Edit Listing Pricing</h3>
                <p className="text-xs text-muted-foreground line-clamp-1">
                  {editingListing.product_name} • {editingListing.variant_name}
                </p>
              </div>
              <button onClick={closeEditModal} className="text-muted-foreground hover:text-foreground">
                <X className="h-5 w-5" />
              </button>
            </div>

            {modalError && (
              <div className="p-3 rounded-lg border border-red-500/30 bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 text-xs flex items-center gap-2">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{modalError}</span>
              </div>
            )}

            <form onSubmit={handleSaveEdit} className="space-y-3.5 text-xs">
              <div>
                <label className="font-medium text-foreground block mb-1">
                  MRP (Maximum Retail Price in ₹)
                </label>
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  value={editOriginalPrice}
                  onChange={(e) => setEditOriginalPrice(e.target.value)}
                  required
                  className="font-mono text-sm"
                />
              </div>

              <div>
                <label className="font-medium text-foreground block mb-1">
                  Store Selling Price (in ₹)
                </label>
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  value={editSellingPrice}
                  onChange={(e) => setEditSellingPrice(e.target.value)}
                  required
                  className="font-mono text-sm font-semibold text-emerald-600"
                />
                <span className="text-[11px] text-muted-foreground">
                  Cannot exceed MRP. Customers pay this price during checkout.
                </span>
              </div>

              <div>
                <label className="font-medium text-foreground block mb-1">
                  Custom Store SKU (Optional)
                </label>
                <Input
                  type="text"
                  placeholder="e.g. BLR-STR-001"
                  value={editSellerSku}
                  onChange={(e) => setEditSellerSku(e.target.value)}
                  maxLength={100}
                  className="font-mono text-xs"
                />
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="activeToggle"
                  checked={editActive}
                  onChange={(e) => setEditActive(e.target.checked)}
                  className="rounded border-border h-4 w-4 text-blue-600"
                />
                <label htmlFor="activeToggle" className="font-medium text-foreground cursor-pointer">
                  Listing is Active and Published to Marketplace
                </label>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t">
                <Button type="button" variant="outline" size="sm" onClick={closeEditModal}>
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={isSavingEdit}
                  className="bg-blue-600 hover:bg-blue-700 text-white"
                >
                  {isSavingEdit ? "Saving..." : "Save Pricing"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
