"use client";

import { useEffect, useState } from "react";
import {
  Tag,
  Plus,
  Search,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Edit2,
  Trash2,
  Info,
  Power,
  Sparkles,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiClient } from "@/lib/api/client";
import type {
  AdminDealListItem,
  AdminCategoryListItem,
  AdminCatalogueProductListItem,
} from "@/types";

export default function AdminDealsPage() {
  const [deals, setDeals] = useState<AdminDealListItem[]>([]);
  const [categories, setCategories] = useState<AdminCategoryListItem[]>([]);
  const [products, setProducts] = useState<AdminCatalogueProductListItem[]>([]);
  const [filterTab, setFilterTab] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Create / Edit Modal
  const [dealModal, setDealModal] = useState<{
    isOpen: boolean;
    mode: "create" | "edit";
    dealId?: string;
    payload: {
      code: string;
      name: string;
      description: string;
      discount_type: "PERCENTAGE" | "FIXED_AMOUNT";
      discount_value: number; // in % or in Rupees
      scope: "PLATFORM_WIDE" | "CATEGORY" | "PRODUCT" | "LISTING";
      category_id?: string;
      product_id?: string;
      listing_id?: string;
      min_order_rupees?: number;
      max_discount_rupees?: number;
      usage_limit?: number;
      valid_from?: string;
      valid_to?: string;
      is_active: boolean;
    };
  } | null>(null);

  const [actionLoading, setActionLoading] = useState(false);

  const loadData = async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const [dealsData, catsData, prodsData] = await Promise.all([
        apiClient.listAdminDeals(),
        apiClient.listAdminCatalogueCategories(),
        apiClient.listAdminCatalogueProducts(),
      ]);
      setDeals(dealsData);
      setCategories(catsData);
      setProducts(prodsData);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to load deals.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleToggleActive = async (deal: AdminDealListItem) => {
    setActionLoading(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      await apiClient.updateAdminDeal(deal.id, {
        is_active: !deal.is_active,
      });
      setSuccessMsg(
        `Deal "${deal.code || deal.name}" ${deal.is_active ? "paused" : "activated"}.`
      );
      await loadData();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to toggle deal status.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeleteDeal = async (id: string, codeOrName: string) => {
    if (!confirm(`Are you sure you want to delete platform deal "${codeOrName}"?`)) return;
    setActionLoading(true);
    setErrorMsg(null);
    try {
      await apiClient.deleteAdminDeal(id);
      setSuccessMsg(`Deal "${codeOrName}" deleted.`);
      await loadData();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to delete deal.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleSaveDeal = async () => {
    if (!dealModal) return;
    setActionLoading(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    const p = dealModal.payload;
    if (!p.code.trim() || !p.name.trim()) {
      setErrorMsg("Promo code and Deal Name are required.");
      setActionLoading(false);
      return;
    }
    if (p.discount_type === "PERCENTAGE" && (p.discount_value <= 0 || p.discount_value > 90)) {
      setErrorMsg("Percentage discount must be between 1% and 90%.");
      setActionLoading(false);
      return;
    }
    if (p.discount_type === "FIXED_AMOUNT" && p.discount_value <= 0) {
      setErrorMsg("Fixed amount discount must be greater than ₹0.");
      setActionLoading(false);
      return;
    }

    // Convert values
    const valuePaise =
      p.discount_type === "FIXED_AMOUNT"
        ? Math.round(p.discount_value * 100)
        : Math.round(p.discount_value);
    const minOrderPaise = p.min_order_rupees
      ? Math.round(p.min_order_rupees * 100)
      : undefined;
    const maxDiscountPaise = p.max_discount_rupees
      ? Math.round(p.max_discount_rupees * 100)
      : undefined;

    try {
      if (dealModal.mode === "create") {
        await apiClient.createAdminDeal({
          code: p.code.trim().toUpperCase(),
          name: p.name.trim(),
          description: p.description.trim() || undefined,
          discount_type: p.discount_type,
          discount_value: valuePaise,
          scope: p.scope,
          category_id: p.scope === "CATEGORY" ? p.category_id : undefined,
          product_id: p.scope === "PRODUCT" ? p.product_id : undefined,
          listing_id: p.scope === "LISTING" ? p.listing_id : undefined,
          min_order_paise: minOrderPaise,
          max_discount_paise: maxDiscountPaise,
          usage_limit: p.usage_limit || undefined,
          valid_from: p.valid_from ? new Date(p.valid_from).toISOString() : undefined,
          valid_to: p.valid_to ? new Date(p.valid_to).toISOString() : undefined,
          is_active: p.is_active,
        });
        setSuccessMsg(`Platform deal "${p.code.toUpperCase()}" created.`);
      } else if (dealModal.dealId) {
        await apiClient.updateAdminDeal(dealModal.dealId, {
          name: p.name.trim(),
          description: p.description.trim() || undefined,
          discount_type: p.discount_type,
          discount_value: valuePaise,
          min_order_paise: minOrderPaise,
          max_discount_paise: maxDiscountPaise,
          usage_limit: p.usage_limit || undefined,
          valid_from: p.valid_from ? new Date(p.valid_from).toISOString() : undefined,
          valid_to: p.valid_to ? new Date(p.valid_to).toISOString() : undefined,
          is_active: p.is_active,
        });
        setSuccessMsg(`Platform deal "${p.code}" updated.`);
      }
      setDealModal(null);
      await loadData();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to save deal.");
    } finally {
      setActionLoading(false);
    }
  };

  const filteredDeals = deals.filter((d) => {
    const status = d.status.toUpperCase();
    const matchesTab =
      filterTab === "ALL" ||
      (filterTab === "ACTIVE" && status === "ACTIVE") ||
      (filterTab === "SCHEDULED" && status === "SCHEDULED") ||
      (filterTab === "PAUSED" && status === "PAUSED") ||
      (filterTab === "EXPIRED" && status === "EXPIRED");
    const matchesSearch =
      !searchQuery ||
      (d.code && d.code.toLowerCase().includes(searchQuery.toLowerCase())) ||
      d.name.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesTab && matchesSearch;
  });

  const getStatusBadge = (status: string) => {
    switch (status.toUpperCase()) {
      case "ACTIVE":
        return <Badge className="bg-emerald-600 text-white font-medium">Active</Badge>;
      case "SCHEDULED":
        return <Badge className="bg-blue-600 text-white font-medium">Scheduled</Badge>;
      case "PAUSED":
        return <Badge variant="outline" className="text-amber-600 border-amber-500 font-medium">Paused</Badge>;
      case "EXPIRED":
        return <Badge variant="outline" className="text-zinc-500 font-medium">Expired</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Sparkles className="h-6 w-6 text-purple-600" />
            Platform Deals & Promotions
          </h1>
          <p className="text-sm text-muted-foreground">
            Schedule platform-wide discount campaigns and targeted promotional vouchers without altering retailer base prices.
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Button
            size="sm"
            onClick={() =>
              setDealModal({
                isOpen: true,
                mode: "create",
                payload: {
                  code: "",
                  name: "",
                  description: "",
                  discount_type: "PERCENTAGE",
                  discount_value: 10,
                  scope: "PLATFORM_WIDE",
                  is_active: true,
                },
              })
            }
            className="bg-purple-600 hover:bg-purple-700 text-white gap-1.5"
          >
            <Plus className="h-4 w-4" />
            New Deal
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={loadData}
            disabled={isLoading}
            className="gap-1.5"
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
          </Button>
        </div>
      </div>

      {/* Critical Invariant Banner */}
      <div className="p-3.5 rounded-xl border border-purple-500/20 bg-purple-500/5 text-xs text-foreground flex items-center gap-3">
        <Info className="h-5 w-5 text-purple-600 shrink-0" />
        <div>
          <strong className="font-semibold text-purple-900 dark:text-purple-300">
            Platform Pricing Integrity:
          </strong>{" "}
          Platform promotions apply dynamically to order quotes.
          Retailers retain absolute authority over their independent catalog listing prices, and deal discounts do not overwrite base unit prices.
        </div>
      </div>

      {/* Alerts */}
      {errorMsg && (
        <div className="p-3.5 rounded-lg border border-red-500/30 bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 text-sm flex items-center gap-2">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}
      {successMsg && (
        <div className="p-3.5 rounded-lg border border-emerald-500/30 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 text-sm flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {/* Filter Tabs & Search */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-card p-3 rounded-xl border">
        <div className="flex flex-wrap gap-1.5 w-full sm:w-auto">
          {["ALL", "ACTIVE", "SCHEDULED", "PAUSED", "EXPIRED"].map((tab) => (
            <button
              key={tab}
              onClick={() => setFilterTab(tab)}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
                filterTab === tab
                  ? "bg-purple-600 text-white"
                  : "bg-muted/60 text-muted-foreground hover:bg-muted hover:text-foreground"
              }`}
            >
              {tab === "ALL" ? "All Deals" : tab.charAt(0) + tab.slice(1).toLowerCase()}
              <span className="ml-1.5 opacity-80">
                ({tab === "ALL"
                  ? deals.length
                  : deals.filter((d) => d.status.toUpperCase() === tab).length})
              </span>
            </button>
          ))}
        </div>
        <div className="relative w-full sm:w-72">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search code or deal name..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9 h-9 text-xs"
          />
        </div>
      </div>

      {/* Deals Grid / List */}
      {isLoading ? (
        <div className="py-16 text-center text-sm text-muted-foreground border rounded-xl bg-card">
          <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-solid border-purple-600 border-r-transparent mb-2" />
          <p>Loading promotions & platform deals...</p>
        </div>
      ) : filteredDeals.length === 0 ? (
        <div className="py-16 text-center text-sm text-muted-foreground border rounded-xl bg-card">
          <Tag className="h-8 w-8 mx-auto mb-2 text-muted-foreground/60" />
          <p className="font-medium text-foreground">No promotions found</p>
          <p className="text-xs text-muted-foreground mt-1">
            {searchQuery || filterTab !== "ALL"
              ? "Try adjusting your search criteria or filter tab."
              : "Launch your first promotional discount code using the button above."}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredDeals.map((d) => {
            const discountLabel =
              d.discount_type === "PERCENTAGE"
                ? `${d.discount_value}% OFF`
                : `₹${(d.discount_value / 100).toFixed(0)} FLAT OFF`;

            return (
              <div
                key={d.id}
                className="bg-card border rounded-xl p-5 shadow-xs flex flex-col justify-between space-y-4 hover:border-purple-500/40 transition-colors"
              >
                <div>
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-base tracking-wider text-purple-700 dark:text-purple-300 bg-purple-50 dark:bg-purple-950/60 px-2.5 py-0.5 rounded-lg border border-purple-200 dark:border-purple-800">
                          {d.code || d.name}
                        </span>
                        {getStatusBadge(d.status)}
                      </div>
                      <h3 className="font-bold text-foreground text-sm mt-2">{d.name}</h3>
                    </div>
                    <div className="text-right shrink-0">
                      <div className="font-extrabold text-base text-emerald-600 dark:text-emerald-400">
                        {discountLabel}
                      </div>
                      {d.max_discount_paise && (
                        <div className="text-[10px] text-muted-foreground">
                          Cap: ₹{(d.max_discount_paise / 100).toFixed(0)}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2 mt-4 pt-3 border-t text-[11px] text-muted-foreground">
                    <div>
                      <span className="font-medium text-foreground">Scope:</span>{" "}
                      <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                        {d.scope}
                      </Badge>
                    </div>
                    <div>
                      <span className="font-medium text-foreground">Min Order:</span>{" "}
                      {d.min_order_paise ? `₹${(d.min_order_paise / 100).toFixed(0)}` : "None"}
                    </div>
                    <div>
                      <span className="font-medium text-foreground">Usage:</span>{" "}
                      {d.times_used} {d.usage_limit ? `/ ${d.usage_limit}` : "uses"}
                    </div>
                    <div>
                      <span className="font-medium text-foreground">Validity:</span>{" "}
                      {d.valid_to
                        ? `Till ${new Date(d.valid_to).toLocaleDateString()}`
                        : "Ongoing"}
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-between border-t pt-3">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleToggleActive(d)}
                    disabled={actionLoading}
                    className="h-7 text-xs px-2.5 gap-1"
                  >
                    <Power className={`h-3.5 w-3.5 ${d.is_active ? "text-red-500" : "text-emerald-500"}`} />
                    {d.is_active ? "Pause Deal" : "Activate"}
                  </Button>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() =>
                        setDealModal({
                          isOpen: true,
                          mode: "edit",
                          dealId: d.id,
                          payload: {
                            code: d.code || "",
                            name: d.name,
                            description: "",
                            discount_type:
                              d.discount_type === "FIXED_AMOUNT" ? "FIXED_AMOUNT" : "PERCENTAGE",
                            discount_value:
                              d.discount_type === "FIXED_AMOUNT"
                                ? d.discount_value / 100
                                : d.discount_value,
                            scope:
                              d.scope === "CATEGORY" ||
                              d.scope === "PRODUCT" ||
                              d.scope === "LISTING"
                                ? d.scope
                                : "PLATFORM_WIDE",
                            category_id: d.category_id || undefined,
                            product_id: d.product_id || undefined,
                            listing_id: d.listing_id || undefined,
                            min_order_rupees: d.min_order_paise
                              ? d.min_order_paise / 100
                              : undefined,
                            max_discount_rupees: d.max_discount_paise
                              ? d.max_discount_paise / 100
                              : undefined,
                            usage_limit: d.usage_limit || undefined,
                            valid_from: d.valid_from
                              ? new Date(d.valid_from).toISOString().slice(0, 16)
                              : undefined,
                            valid_to: d.valid_to
                              ? new Date(d.valid_to).toISOString().slice(0, 16)
                              : undefined,
                            is_active: d.is_active,
                          },
                        })
                      }
                      className="h-7 w-7 p-0"
                    >
                      <Edit2 className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDeleteDeal(d.id, d.code || d.name)}
                      className="h-7 w-7 p-0 text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Deal Create / Edit Modal */}
      {dealModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
          <div className="bg-card border rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto shadow-2xl p-6 space-y-4">
            <h3 className="text-lg font-bold text-foreground">
              {dealModal.mode === "create" ? "Create Promotional Deal" : "Edit Promotional Deal"}
            </h3>

            <div className="space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold text-muted-foreground block mb-1">
                    Promo Code *
                  </label>
                  <Input
                    placeholder="e.g. FESTIVE20"
                    value={dealModal.payload.code}
                    disabled={dealModal.mode === "edit"}
                    onChange={(e) =>
                      setDealModal({
                        ...dealModal,
                        payload: { ...dealModal.payload, code: e.target.value.toUpperCase() },
                      })
                    }
                    className="h-9 text-xs font-mono font-bold"
                  />
                </div>
                <div>
                  <label className="font-semibold text-muted-foreground block mb-1">
                    Deal Name *
                  </label>
                  <Input
                    placeholder="e.g. Festival Mega Discount"
                    value={dealModal.payload.name}
                    onChange={(e) =>
                      setDealModal({
                        ...dealModal,
                        payload: { ...dealModal.payload, name: e.target.value },
                      })
                    }
                    className="h-9 text-xs"
                  />
                </div>
              </div>

              <div>
                <label className="font-semibold text-muted-foreground block mb-1">
                  Description
                </label>
                <Input
                  placeholder="e.g. Get 20% off on all items across the platform"
                  value={dealModal.payload.description}
                  onChange={(e) =>
                    setDealModal({
                      ...dealModal,
                      payload: { ...dealModal.payload, description: e.target.value },
                    })
                  }
                  className="h-9 text-xs"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold text-muted-foreground block mb-1">
                    Discount Type
                  </label>
                  <select
                    value={dealModal.payload.discount_type}
                    onChange={(e) =>
                      setDealModal({
                        ...dealModal,
                        payload: {
                          ...dealModal.payload,
                          discount_type: e.target.value as "PERCENTAGE" | "FIXED_AMOUNT",
                        },
                      })
                    }
                    className="w-full h-9 text-xs rounded-lg border bg-background px-3 outline-hidden"
                  >
                    <option value="PERCENTAGE">Percentage (%)</option>
                    <option value="FIXED_AMOUNT">Fixed Amount (₹)</option>
                  </select>
                </div>
                <div>
                  <label className="font-semibold text-muted-foreground block mb-1">
                    Discount Value {dealModal.payload.discount_type === "PERCENTAGE" ? "(%)" : "(₹)"} *
                  </label>
                  <Input
                    type="number"
                    min={1}
                    max={dealModal.payload.discount_type === "PERCENTAGE" ? 90 : 100000}
                    value={dealModal.payload.discount_value}
                    onChange={(e) =>
                      setDealModal({
                        ...dealModal,
                        payload: {
                          ...dealModal.payload,
                          discount_value: parseFloat(e.target.value) || 0,
                        },
                      })
                    }
                    className="h-9 text-xs font-semibold"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold text-muted-foreground block mb-1">
                    Promotional Scope
                  </label>
                  <select
                    value={dealModal.payload.scope}
                    disabled={dealModal.mode === "edit"}
                    onChange={(e) =>
                      setDealModal({
                        ...dealModal,
                        payload: {
                          ...dealModal.payload,
                          scope: e.target.value as "PLATFORM_WIDE" | "CATEGORY" | "PRODUCT" | "LISTING",
                        },
                      })
                    }
                    className="w-full h-9 text-xs rounded-lg border bg-background px-3 outline-hidden"
                  >
                    <option value="PLATFORM_WIDE">Platform-Wide (All Products)</option>
                    <option value="CATEGORY">Target Category</option>
                    <option value="PRODUCT">Target Canonical Product</option>
                    <option value="LISTING">Target Specific Listing</option>
                  </select>
                </div>

                {dealModal.payload.scope === "CATEGORY" && (
                  <div>
                    <label className="font-semibold text-muted-foreground block mb-1">
                      Select Category
                    </label>
                    <select
                      value={dealModal.payload.category_id || ""}
                      onChange={(e) =>
                        setDealModal({
                          ...dealModal,
                          payload: { ...dealModal.payload, category_id: e.target.value },
                        })
                      }
                      className="w-full h-9 text-xs rounded-lg border bg-background px-3 outline-hidden"
                    >
                      <option value="">Select Category...</option>
                      {categories.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                {dealModal.payload.scope === "PRODUCT" && (
                  <div>
                    <label className="font-semibold text-muted-foreground block mb-1">
                      Select Canonical Product
                    </label>
                    <select
                      value={dealModal.payload.product_id || ""}
                      onChange={(e) =>
                        setDealModal({
                          ...dealModal,
                          payload: { ...dealModal.payload, product_id: e.target.value },
                        })
                      }
                      className="w-full h-9 text-xs rounded-lg border bg-background px-3 outline-hidden"
                    >
                      <option value="">Select Product...</option>
                      {products.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                {dealModal.payload.scope === "LISTING" && (
                  <div>
                    <label className="font-semibold text-muted-foreground block mb-1">
                      Listing UUID
                    </label>
                    <Input
                      placeholder="e.g. 550e8400-e29b-41d4-a716-446655440000"
                      value={dealModal.payload.listing_id || ""}
                      onChange={(e) =>
                        setDealModal({
                          ...dealModal,
                          payload: { ...dealModal.payload, listing_id: e.target.value },
                        })
                      }
                      className="h-9 text-xs font-mono"
                    />
                  </div>
                )}
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold text-muted-foreground block mb-1">
                    Min Order Amount (₹)
                  </label>
                  <Input
                    type="number"
                    min={0}
                    placeholder="Optional (e.g. 499)"
                    value={dealModal.payload.min_order_rupees ?? ""}
                    onChange={(e) =>
                      setDealModal({
                        ...dealModal,
                        payload: {
                          ...dealModal.payload,
                          min_order_rupees: e.target.value ? parseFloat(e.target.value) : undefined,
                        },
                      })
                    }
                    className="h-9 text-xs"
                  />
                </div>
                <div>
                  <label className="font-semibold text-muted-foreground block mb-1">
                    Max Discount Cap (₹)
                  </label>
                  <Input
                    type="number"
                    min={0}
                    placeholder="Optional (e.g. 500)"
                    value={dealModal.payload.max_discount_rupees ?? ""}
                    onChange={(e) =>
                      setDealModal({
                        ...dealModal,
                        payload: {
                          ...dealModal.payload,
                          max_discount_rupees: e.target.value ? parseFloat(e.target.value) : undefined,
                        },
                      })
                    }
                    className="h-9 text-xs"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="font-semibold text-muted-foreground block mb-1">
                    Usage Limit
                  </label>
                  <Input
                    type="number"
                    min={1}
                    placeholder="e.g. 100"
                    value={dealModal.payload.usage_limit ?? ""}
                    onChange={(e) =>
                      setDealModal({
                        ...dealModal,
                        payload: {
                          ...dealModal.payload,
                          usage_limit: e.target.value ? parseInt(e.target.value, 10) : undefined,
                        },
                      })
                    }
                    className="h-9 text-xs"
                  />
                </div>
                <div>
                  <label className="font-semibold text-muted-foreground block mb-1">
                    Valid From
                  </label>
                  <Input
                    type="datetime-local"
                    value={dealModal.payload.valid_from ?? ""}
                    onChange={(e) =>
                      setDealModal({
                        ...dealModal,
                        payload: { ...dealModal.payload, valid_from: e.target.value },
                      })
                    }
                    className="h-9 text-xs"
                  />
                </div>
                <div>
                  <label className="font-semibold text-muted-foreground block mb-1">
                    Valid To
                  </label>
                  <Input
                    type="datetime-local"
                    value={dealModal.payload.valid_to ?? ""}
                    onChange={(e) =>
                      setDealModal({
                        ...dealModal,
                        payload: { ...dealModal.payload, valid_to: e.target.value },
                      })
                    }
                    className="h-9 text-xs"
                  />
                </div>
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="deal_active"
                  checked={dealModal.payload.is_active}
                  onChange={(e) =>
                    setDealModal({
                      ...dealModal,
                      payload: { ...dealModal.payload, is_active: e.target.checked },
                    })
                  }
                  className="rounded border-input text-purple-600 focus:ring-purple-500"
                />
                <label htmlFor="deal_active" className="text-xs font-medium cursor-pointer">
                  Promotional Deal Active
                </label>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setDealModal(null)}
                disabled={actionLoading}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handleSaveDeal}
                disabled={actionLoading}
                className="bg-purple-600 hover:bg-purple-700 text-white"
              >
                {actionLoading ? "Saving..." : "Save Deal"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
