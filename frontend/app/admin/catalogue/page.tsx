"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  LayoutGrid,
  Plus,
  Search,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Layers,
  Edit2,
  Trash2,
  Info,
  X,
  Package,
  FolderPlus,
  FileCheck2,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiClient } from "@/lib/api/client";
import type {
  AdminCatalogueProductListItem,
  AdminCatalogueProductDetailResponse,
  AdminCategoryListItem,
} from "@/types";

export default function AdminCataloguePage() {
  const [products, setProducts] = useState<AdminCatalogueProductListItem[]>([]);
  const [categories, setCategories] = useState<AdminCategoryListItem[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string>("ALL");
  const [isLoading, setIsLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Variant manager modal / expanded product
  const [activeProduct, setActiveProduct] = useState<AdminCatalogueProductDetailResponse | null>(null);

  // Product Create/Edit Modal
  const [productModal, setProductModal] = useState<{
    isOpen: boolean;
    mode: "create" | "edit";
    productId?: string;
    payload: {
      name: string;
      slug: string;
      category_id: string;
      brand: string;
      description: string;
      imageUrl: string;
      is_active: boolean;
    };
  } | null>(null);

  // Variant Create/Edit Modal
  const [variantModal, setVariantModal] = useState<{
    isOpen: boolean;
    mode: "create" | "edit";
    variantId?: string;
    payload: {
      sku: string;
      name: string;
      attributesText: string;
      is_active: boolean;
    };
  } | null>(null);

  // Category Create Modal
  const [categoryModal, setCategoryModal] = useState<{
    isOpen: boolean;
    name: string;
    slug: string;
    description: string;
  } | null>(null);

  const [actionLoading, setActionLoading] = useState(false);

  const loadData = async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const [prods, cats] = await Promise.all([
        apiClient.listAdminCatalogueProducts(),
        apiClient.listAdminCatalogueCategories(),
      ]);
      setProducts(prods);
      setCategories(cats);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to load catalogue data.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const openManageProduct = async (productId: string) => {
    setErrorMsg(null);
    try {
      const detail = await apiClient.getAdminCatalogueProduct(productId);
      setActiveProduct(detail);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to fetch product details.");
    }
  };

  const handleProductSubmit = async () => {
    if (!productModal) return;
    setActionLoading(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      if (productModal.mode === "create") {
        await apiClient.createAdminCatalogueProduct({
          name: productModal.payload.name.trim(),
          slug: productModal.payload.slug.trim() || undefined,
          category_id: productModal.payload.category_id,
          brand: productModal.payload.brand.trim() || "Generic",
          description: productModal.payload.description.trim() || undefined,
          image_urls: productModal.payload.imageUrl.trim()
            ? [productModal.payload.imageUrl.trim()]
            : undefined,
          is_active: productModal.payload.is_active,
        });
        setSuccessMsg(`Created canonical product "${productModal.payload.name}".`);
      } else if (productModal.productId) {
        await apiClient.updateAdminCatalogueProduct(productModal.productId, {
          name: productModal.payload.name.trim(),
          brand: productModal.payload.brand.trim() || undefined,
          description: productModal.payload.description.trim() || undefined,
          is_active: productModal.payload.is_active,
        });
        setSuccessMsg(`Updated canonical product "${productModal.payload.name}".`);
      }
      setProductModal(null);
      await loadData();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to save product.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeleteProduct = async (id: string, name: string) => {
    if (!confirm(`Are you sure you want to delete canonical product "${name}"?`)) return;
    setActionLoading(true);
    setErrorMsg(null);
    try {
      await apiClient.deleteAdminCatalogueProduct(id);
      setSuccessMsg(`Product "${name}" deleted.`);
      if (activeProduct?.id === id) setActiveProduct(null);
      await loadData();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to delete product.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleVariantSubmit = async () => {
    if (!variantModal || !activeProduct) return;
    setActionLoading(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    let parsedAttributes: Record<string, unknown> = {};
    if (variantModal.payload.attributesText.trim()) {
      try {
        parsedAttributes = JSON.parse(variantModal.payload.attributesText.trim());
      } catch {
        setErrorMsg('Variant attributes must be valid JSON (e.g. {"color": "Black", "size": "XL"}).');
        setActionLoading(false);
        return;
      }
    }

    try {
      if (variantModal.mode === "create") {
        await apiClient.createAdminCatalogueVariant(activeProduct.id, {
          sku: variantModal.payload.sku.trim(),
          name: variantModal.payload.name.trim() || "Standard Variant",
          attributes: parsedAttributes,
          is_active: variantModal.payload.is_active,
        });
        setSuccessMsg(`Variant SKU ${variantModal.payload.sku} created.`);
      } else if (variantModal.variantId) {
        await apiClient.updateAdminCatalogueVariant(variantModal.variantId, {
          sku: variantModal.payload.sku.trim(),
          name: variantModal.payload.name.trim() || undefined,
          attributes: parsedAttributes,
          is_active: variantModal.payload.is_active,
        });
        setSuccessMsg(`Variant SKU ${variantModal.payload.sku} updated.`);
      }
      setVariantModal(null);
      // Refresh active product variants
      const updated = await apiClient.getAdminCatalogueProduct(activeProduct.id);
      setActiveProduct(updated);
      await loadData();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to save variant.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeleteVariant = async (variantId: string, sku: string) => {
    if (!activeProduct || !confirm(`Delete variant SKU "${sku}"?`)) return;
    setActionLoading(true);
    setErrorMsg(null);
    try {
      await apiClient.deleteAdminCatalogueVariant(variantId);
      setSuccessMsg(`Variant SKU "${sku}" deleted.`);
      const updated = await apiClient.getAdminCatalogueProduct(activeProduct.id);
      setActiveProduct(updated);
      await loadData();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to delete variant.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleCategorySubmit = async () => {
    if (!categoryModal) return;
    setActionLoading(true);
    setErrorMsg(null);
    try {
      await apiClient.createAdminCatalogueCategory({
        name: categoryModal.name.trim(),
        slug: categoryModal.slug.trim() || undefined,
        description: categoryModal.description.trim() || undefined,
      });
      setSuccessMsg(`Created category "${categoryModal.name}".`);
      setCategoryModal(null);
      await loadData();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to create category.");
    } finally {
      setActionLoading(false);
    }
  };

  const filteredProducts = products.filter((p) => {
    const matchesCat =
      selectedCategory === "ALL" || p.category_id === selectedCategory;
    const matchesSearch =
      !searchQuery ||
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.slug.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (p.brand && p.brand.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (p.category_name && p.category_name.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchesCat && matchesSearch;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <LayoutGrid className="h-6 w-6 text-purple-600" />
            Platform Catalogue Manager
          </h1>
          <p className="text-sm text-muted-foreground">
            Govern canonical master products, variant hierarchies, and taxonomies without altering retailer selling prices.
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Link href="/admin/passport">
            <Button
              variant="outline"
              size="sm"
              className="text-xs font-semibold border-emerald-600/40 text-emerald-700 hover:bg-emerald-50 dark:hover:bg-emerald-950/30 gap-1.5 cursor-pointer"
            >
              <FileCheck2 className="h-4 w-4 text-emerald-600" />
              Passport Moderation Queue
            </Button>
          </Link>
          <Button
            variant="outline"
            size="sm"
            onClick={() =>
              setCategoryModal({ isOpen: true, name: "", slug: "", description: "" })
            }
            className="gap-1.5"
          >
            <FolderPlus className="h-4 w-4" />
            New Category
          </Button>
          <Button
            size="sm"
            onClick={() =>
              setProductModal({
                isOpen: true,
                mode: "create",
                payload: {
                  name: "",
                  slug: "",
                  category_id: categories[0]?.id || "",
                  brand: "",
                  description: "",
                  imageUrl: "",
                  is_active: true,
                },
              })
            }
            className="bg-purple-600 hover:bg-purple-700 text-white gap-1.5"
          >
            <Plus className="h-4 w-4" />
            New Product
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
            Canonical Specifications Invariant:
          </strong>{" "}
          Editing canonical master products, attributes, or variants updates the platform catalogue blueprint.
          It does not alter existing retailer listings, independent selling prices, or retailer stock levels.
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

      {/* Filters */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-card p-3 rounded-xl border">
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <span className="text-xs text-muted-foreground whitespace-nowrap">Category:</span>
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="h-9 text-xs rounded-lg border bg-background px-3 outline-hidden"
          >
            <option value="ALL">All Categories ({products.length})</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
        <div className="relative w-full sm:w-72">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search product name, slug, brand..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9 h-9 text-xs"
          />
        </div>
      </div>

      {/* Products Table */}
      <div className="rounded-xl border bg-card shadow-xs overflow-hidden">
        {isLoading ? (
          <div className="py-16 text-center text-sm text-muted-foreground">
            <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-solid border-purple-600 border-r-transparent mb-2" />
            <p>Loading canonical catalogue items...</p>
          </div>
        ) : filteredProducts.length === 0 ? (
          <div className="py-16 text-center text-sm text-muted-foreground">
            <Package className="h-8 w-8 mx-auto mb-2 text-muted-foreground/60" />
            <p className="font-medium text-foreground">No canonical products found</p>
            <p className="text-xs text-muted-foreground mt-1">
              {searchQuery || selectedCategory !== "ALL"
                ? "Try adjusting your search criteria or category filter."
                : "Add your first canonical product using the button above."}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-muted/50 border-b text-muted-foreground font-semibold">
                <tr>
                  <th className="px-4 py-3">Product Name & Slug</th>
                  <th className="px-4 py-3">Category</th>
                  <th className="px-4 py-3">Brand</th>
                  <th className="px-4 py-3">Variants</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filteredProducts.map((p) => (
                  <tr key={p.id} className="hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-3">
                      <div className="font-semibold text-foreground text-sm">{p.name}</div>
                      <div className="text-[11px] text-muted-foreground font-mono">
                        slug: {p.slug}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant="outline" className="text-xs">
                        {p.category_name || "Uncategorized"}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-foreground font-medium">
                      {p.brand || "—"}
                    </td>
                    <td className="px-4 py-3">
                      <Badge className="bg-purple-100 text-purple-700 dark:bg-purple-950 dark:text-purple-300 font-medium">
                        {p.variants_count} variant{p.variants_count === 1 ? "" : "s"}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      {p.is_active ? (
                        <Badge className="bg-emerald-600 text-white font-medium">Active</Badge>
                      ) : (
                        <Badge variant="outline" className="text-muted-foreground">Inactive</Badge>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => openManageProduct(p.id)}
                          className="h-7 text-xs px-2.5 gap-1"
                        >
                          <Layers className="h-3.5 w-3.5 text-purple-600" />
                          Variants ({p.variants_count})
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={async () => {
                            try {
                              const detail = await apiClient.getAdminCatalogueProduct(p.id);
                              setProductModal({
                                isOpen: true,
                                mode: "edit",
                                productId: p.id,
                                payload: {
                                  name: detail.name,
                                  slug: detail.slug,
                                  category_id: detail.category_id,
                                  brand: detail.brand,
                                  description: detail.description || "",
                                  imageUrl: detail.images[0]?.url || "",
                                  is_active: detail.is_active,
                                },
                              });
                            } catch (e: unknown) {
                              setErrorMsg(e instanceof Error ? e.message : "Failed to load product for editing");
                            }
                          }}
                          className="h-7 w-7 p-0"
                          title="Edit Product"
                        >
                          <Edit2 className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteProduct(p.id, p.name)}
                          className="h-7 w-7 p-0 text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950"
                          title="Delete Product"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Product Variants Drawer / Modal */}
      {activeProduct && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
          <div className="bg-card border rounded-2xl w-full max-w-3xl max-h-[90vh] overflow-y-auto shadow-2xl p-6 space-y-6">
            <div className="flex items-center justify-between border-b pb-4">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-xl font-bold tracking-tight text-foreground">
                    {activeProduct.name}
                  </h2>
                  <Badge variant="outline" className="text-xs">
                    {activeProduct.category_name}
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground mt-0.5 font-mono">
                  slug: {activeProduct.slug} • Brand: {activeProduct.brand}
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setActiveProduct(null)}
                className="h-8 w-8 p-0"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>

            {/* Variants Sub-header */}
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold tracking-tight text-foreground">
                  Canonical Variants ({activeProduct.variants.length})
                </h3>
                <p className="text-xs text-muted-foreground">
                  Each variant defines a unique SKU/specification that merchants can independently stock and price.
                </p>
              </div>
              <Button
                size="sm"
                onClick={() =>
                  setVariantModal({
                    isOpen: true,
                    mode: "create",
                    payload: {
                      sku: `${activeProduct.slug.slice(0, 8).toUpperCase()}-${Math.floor(100 + Math.random() * 900)}`,
                      name: "Standard Variant",
                      attributesText: "{}",
                      is_active: true,
                    },
                  })
                }
                className="bg-purple-600 hover:bg-purple-700 text-white text-xs gap-1"
              >
                <Plus className="h-3.5 w-3.5" />
                Add Variant
              </Button>
            </div>

            {/* Variants List */}
            {activeProduct.variants.length === 0 ? (
              <div className="p-8 text-center text-xs text-muted-foreground border rounded-xl bg-muted/20">
                No variants defined for this product yet. Add at least one variant SKU to make this product listable by merchants.
              </div>
            ) : (
              <div className="border rounded-xl divide-y text-xs overflow-hidden">
                {activeProduct.variants.map((v) => (
                  <div key={v.id} className="p-3.5 bg-card flex items-center justify-between gap-4">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-foreground">{v.sku}</span>
                        <span className="text-muted-foreground font-medium">• {v.name}</span>
                        {v.is_active ? (
                          <Badge className="bg-emerald-600 text-white text-[10px]">Active</Badge>
                        ) : (
                          <Badge variant="outline" className="text-[10px]">Inactive</Badge>
                        )}
                      </div>
                      {v.attributes && Object.keys(v.attributes).length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1">
                          {Object.entries(v.attributes).map(([k, val]) => (
                            <span
                              key={k}
                              className="px-1.5 py-0.5 rounded bg-muted text-[10px] text-muted-foreground font-mono"
                            >
                              {k}: {String(val)}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() =>
                          setVariantModal({
                            isOpen: true,
                            mode: "edit",
                            variantId: v.id,
                            payload: {
                              sku: v.sku,
                              name: v.name,
                              attributesText: JSON.stringify(v.attributes || {}, null, 2),
                              is_active: v.is_active,
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
                        onClick={() => handleDeleteVariant(v.id, v.sku)}
                        className="h-7 w-7 p-0 text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="flex justify-end border-t pt-4">
              <Button variant="outline" size="sm" onClick={() => setActiveProduct(null)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Product Create / Edit Modal */}
      {productModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
          <div className="bg-card border rounded-2xl w-full max-w-lg shadow-2xl p-6 space-y-4">
            <h3 className="text-lg font-bold text-foreground">
              {productModal.mode === "create" ? "Add Canonical Product" : "Edit Canonical Product"}
            </h3>

            <div className="space-y-3 text-xs">
              <div>
                <label className="font-semibold text-muted-foreground block mb-1">
                  Product Name *
                </label>
                <Input
                  placeholder="e.g. Sony WH-1000XM5 Wireless Headphones"
                  value={productModal.payload.name}
                  onChange={(e) => {
                    const name = e.target.value;
                    const autoSlug =
                      productModal.mode === "create"
                        ? name
                            .toLowerCase()
                            .replace(/[^a-z0-9]+/g, "-")
                            .replace(/(^-|-$)/g, "")
                        : productModal.payload.slug;
                    setProductModal({
                      ...productModal,
                      payload: { ...productModal.payload, name, slug: autoSlug },
                    });
                  }}
                  className="h-9 text-xs"
                />
              </div>

              {productModal.mode === "create" && (
                <div>
                  <label className="font-semibold text-muted-foreground block mb-1">
                    Canonical Slug
                  </label>
                  <Input
                    placeholder="sony-wh-1000xm5"
                    value={productModal.payload.slug}
                    onChange={(e) =>
                      setProductModal({
                        ...productModal,
                        payload: { ...productModal.payload, slug: e.target.value },
                      })
                    }
                    className="h-9 text-xs font-mono"
                  />
                </div>
              )}

              {productModal.mode === "create" && (
                <div>
                  <label className="font-semibold text-muted-foreground block mb-1">
                    Category *
                  </label>
                  <select
                    value={productModal.payload.category_id}
                    onChange={(e) =>
                      setProductModal({
                        ...productModal,
                        payload: { ...productModal.payload, category_id: e.target.value },
                      })
                    }
                    className="w-full h-9 text-xs rounded-lg border bg-background px-3 outline-hidden"
                  >
                    {categories.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold text-muted-foreground block mb-1">
                    Brand Name *
                  </label>
                  <Input
                    placeholder="Sony"
                    value={productModal.payload.brand}
                    onChange={(e) =>
                      setProductModal({
                        ...productModal,
                        payload: { ...productModal.payload, brand: e.target.value },
                      })
                    }
                    className="h-9 text-xs"
                  />
                </div>
                {productModal.mode === "create" && (
                  <div>
                    <label className="font-semibold text-muted-foreground block mb-1">
                      Image URL
                    </label>
                    <Input
                      placeholder="https://..."
                      value={productModal.payload.imageUrl}
                      onChange={(e) =>
                        setProductModal({
                          ...productModal,
                          payload: { ...productModal.payload, imageUrl: e.target.value },
                        })
                      }
                      className="h-9 text-xs"
                    />
                  </div>
                )}
              </div>

              <div>
                <label className="font-semibold text-muted-foreground block mb-1">
                  Canonical Description
                </label>
                <textarea
                  rows={3}
                  placeholder="Platform-wide product description and specifications..."
                  value={productModal.payload.description}
                  onChange={(e) =>
                    setProductModal({
                      ...productModal,
                      payload: { ...productModal.payload, description: e.target.value },
                    })
                  }
                  className="w-full text-xs rounded-lg border bg-background p-2.5 outline-hidden focus:ring-2 focus:ring-purple-500"
                />
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="prod_active"
                  checked={productModal.payload.is_active}
                  onChange={(e) =>
                    setProductModal({
                      ...productModal,
                      payload: { ...productModal.payload, is_active: e.target.checked },
                    })
                  }
                  className="rounded border-input text-purple-600 focus:ring-purple-500"
                />
                <label htmlFor="prod_active" className="text-xs font-medium cursor-pointer">
                  Product Active in Platform Catalogue
                </label>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setProductModal(null)}
                disabled={actionLoading}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handleProductSubmit}
                disabled={actionLoading || !productModal.payload.name.trim()}
                className="bg-purple-600 hover:bg-purple-700 text-white"
              >
                {actionLoading ? "Saving..." : "Save Product"}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Variant Create / Edit Modal */}
      {variantModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
          <div className="bg-card border rounded-2xl w-full max-w-md shadow-2xl p-6 space-y-4">
            <h3 className="text-lg font-bold text-foreground">
              {variantModal.mode === "create" ? "Add Variant SKU" : "Edit Variant SKU"}
            </h3>

            <div className="space-y-3 text-xs">
              <div>
                <label className="font-semibold text-muted-foreground block mb-1">
                  Variant SKU *
                </label>
                <Input
                  placeholder="e.g. SONY-WH1000XM5-BLK"
                  value={variantModal.payload.sku}
                  onChange={(e) =>
                    setVariantModal({
                      ...variantModal,
                      payload: { ...variantModal.payload, sku: e.target.value },
                    })
                  }
                  className="h-9 text-xs font-mono"
                />
              </div>

              <div>
                <label className="font-semibold text-muted-foreground block mb-1">
                  Variant Name *
                </label>
                <Input
                  placeholder="e.g. Midnight Black (30 Hr Battery)"
                  value={variantModal.payload.name}
                  onChange={(e) =>
                    setVariantModal({
                      ...variantModal,
                      payload: { ...variantModal.payload, name: e.target.value },
                    })
                  }
                  className="h-9 text-xs"
                />
              </div>

              <div>
                <label className="font-semibold text-muted-foreground block mb-1">
                  Variant Attributes (JSON)
                </label>
                <textarea
                  rows={3}
                  placeholder='{"color": "Black", "connectivity": "Bluetooth 5.2"}'
                  value={variantModal.payload.attributesText}
                  onChange={(e) =>
                    setVariantModal({
                      ...variantModal,
                      payload: { ...variantModal.payload, attributesText: e.target.value },
                    })
                  }
                  className="w-full text-xs font-mono rounded-lg border bg-background p-2.5 outline-hidden focus:ring-2 focus:ring-purple-500"
                />
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="var_active"
                  checked={variantModal.payload.is_active}
                  onChange={(e) =>
                    setVariantModal({
                      ...variantModal,
                      payload: { ...variantModal.payload, is_active: e.target.checked },
                    })
                  }
                  className="rounded border-input text-purple-600 focus:ring-purple-500"
                />
                <label htmlFor="var_active" className="text-xs font-medium cursor-pointer">
                  Variant Active
                </label>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setVariantModal(null)}
                disabled={actionLoading}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handleVariantSubmit}
                disabled={actionLoading || !variantModal.payload.sku.trim()}
                className="bg-purple-600 hover:bg-purple-700 text-white"
              >
                {actionLoading ? "Saving..." : "Save Variant"}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Category Create Modal */}
      {categoryModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
          <div className="bg-card border rounded-2xl w-full max-w-md shadow-2xl p-6 space-y-4">
            <h3 className="text-lg font-bold text-foreground">Add Master Category</h3>

            <div className="space-y-3 text-xs">
              <div>
                <label className="font-semibold text-muted-foreground block mb-1">
                  Category Name *
                </label>
                <Input
                  placeholder="e.g. Consumer Electronics"
                  value={categoryModal.name}
                  onChange={(e) => {
                    const name = e.target.value;
                    const slug = name
                      .toLowerCase()
                      .replace(/[^a-z0-9]+/g, "-")
                      .replace(/(^-|-$)/g, "");
                    setCategoryModal({ ...categoryModal, name, slug });
                  }}
                  className="h-9 text-xs"
                />
              </div>

              <div>
                <label className="font-semibold text-muted-foreground block mb-1">
                  Category Slug
                </label>
                <Input
                  placeholder="consumer-electronics"
                  value={categoryModal.slug}
                  onChange={(e) =>
                    setCategoryModal({ ...categoryModal, slug: e.target.value })
                  }
                  className="h-9 text-xs font-mono"
                />
              </div>

              <div>
                <label className="font-semibold text-muted-foreground block mb-1">
                  Description
                </label>
                <textarea
                  rows={2}
                  placeholder="Category overview..."
                  value={categoryModal.description}
                  onChange={(e) =>
                    setCategoryModal({ ...categoryModal, description: e.target.value })
                  }
                  className="w-full text-xs rounded-lg border bg-background p-2.5 outline-hidden focus:ring-2 focus:ring-purple-500"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCategoryModal(null)}
                disabled={actionLoading}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handleCategorySubmit}
                disabled={actionLoading || !categoryModal.name.trim()}
                className="bg-purple-600 hover:bg-purple-700 text-white"
              >
                {actionLoading ? "Creating..." : "Create Category"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
