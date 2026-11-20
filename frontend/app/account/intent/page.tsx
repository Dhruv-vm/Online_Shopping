"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiClient, ApiClientError } from "@/lib/api/client";
import { ProtectedRoute } from "@/components/auth/protected-route";
import { AccountNav } from "@/components/account/account-nav";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { formatPrice } from "@/lib/utils";
import type {
  CustomerPreferenceProfile,
  RecurringIntention,
  IntentMemoryItem,
  ShoppingPriority,
  Frequency,
} from "@/types";
import {
  Sparkles,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Plus,
  Trash2,
  Calendar,
  Compass,
  Tag,
  ToggleLeft,
  ToggleRight,
  Sliders,
  DollarSign,
  Store,
  Layers,
  ArrowRight,
  Info,
  X,
  Play,
  Pause,
  AlertTriangle,
} from "lucide-react";

const SHOPPING_PRIORITIES: { id: ShoppingPriority; label: string; desc: string }[] = [
  { id: "BALANCED", label: "Balanced", desc: "Best combination of price, quality and ratings" },
  { id: "LOWEST_PRICE", label: "Lowest Price", desc: "Always prioritize the most economical deals" },
  { id: "QUALITY", label: "Top Quality", desc: "Prioritize top-rated and verified premium products" },
  { id: "DURABILITY", label: "Durability", desc: "Long-lasting construction and dependable brands" },
  { id: "CONVENIENCE", label: "Convenience", desc: "Immediate stock and swift multi-item checkout" },
];

const FREQUENCIES: { id: Frequency; label: string }[] = [
  { id: "WEEKLY", label: "Every Week" },
  { id: "BIWEEKLY", label: "Every 2 Weeks" },
  { id: "MONTHLY", label: "Monthly" },
  { id: "QUARTERLY", label: "Quarterly" },
  { id: "SEASONAL", label: "Seasonal" },
];

export default function IntentMemoryPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  // Intent State
  const [personalizationEnabled, setPersonalizationEnabled] = useState(true);
  const [profile, setProfile] = useState<CustomerPreferenceProfile | null>(null);
  const [intentions, setIntentions] = useState<RecurringIntention[]>([]);
  const [memories, setMemories] = useState<IntentMemoryItem[]>([]);

  // Profile Form State
  const [preferredBrands, setPreferredBrands] = useState<string[]>([]);
  const [newBrandInput, setNewBrandInput] = useState("");
  const [preferredRetailers, setPreferredRetailers] = useState<string[]>([]);
  const [newRetailerInput, setNewRetailerInput] = useState("");
  const [selectedPriorities, setSelectedPriorities] = useState<string[]>([]);
  const [minPriceRupees, setMinPriceRupees] = useState<string>("");
  const [maxPriceRupees, setMaxPriceRupees] = useState<string>("");

  // New Intention Form State
  const [showNewIntentionModal, setShowNewIntentionModal] = useState(false);
  const [intentionTitle, setIntentionTitle] = useState("");
  const [intentionFrequency, setIntentionFrequency] = useState<string>("MONTHLY");
  const [intentionBudgetRupees, setIntentionBudgetRupees] = useState("");
  const [intentionNotes, setIntentionNotes] = useState("");

  // New Memory Item Form State
  const [showNewMemoryModal, setShowNewMemoryModal] = useState(false);
  const [memoryKey, setMemoryKey] = useState("");
  const [memorySummary, setMemorySummary] = useState("");

  // Clear All Confirmation
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  const loadIntentData = useCallback(async () => {
    try {
      setLoading(true);
      const overview = await apiClient.getIntentOverview();
      setPersonalizationEnabled(overview.personalization_enabled);
      setProfile(overview.profile || null);
      setIntentions(overview.recurring_intentions || []);
      setMemories(overview.memories || []);

      if (overview.profile) {
        setPreferredBrands(overview.profile.preferred_brands || []);
        setPreferredRetailers(overview.profile.preferred_retailers || []);
        setSelectedPriorities(overview.profile.shopping_priorities || ["BALANCED"]);
        const range = overview.profile.preferred_price_range || {};
        if (range.min_paise !== undefined && range.min_paise !== null) {
          setMinPriceRupees(String(Math.round(range.min_paise / 100)));
        } else {
          setMinPriceRupees("");
        }
        if (range.max_paise !== undefined && range.max_paise !== null) {
          setMaxPriceRupees(String(Math.round(range.max_paise / 100)));
        } else {
          setMaxPriceRupees("");
        }
      }
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setFeedback({ type: "error", message: err.message || "Failed to load intent memory." });
      } else {
        setFeedback({ type: "error", message: "Network error loading shopping memory." });
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadIntentData();
  }, [loadIntentData]);

  // Handle Consent Toggle
  const handleToggleConsent = async () => {
    try {
      setActionLoading(true);
      const nextConsent = !personalizationEnabled;
      const res = await apiClient.updatePersonalizationConsent(nextConsent);
      setPersonalizationEnabled(res.personalization_enabled);
      setFeedback({ type: "success", message: res.message });
    } catch (err: unknown) {
      const msg = err instanceof ApiClientError ? err.message : "Failed to update personalization setting.";
      setFeedback({ type: "error", message: msg });
    } finally {
      setActionLoading(false);
    }
  };

  // Add Brand Chip
  const handleAddBrand = (e: React.FormEvent) => {
    e.preventDefault();
    const clean = newBrandInput.trim();
    if (clean && !preferredBrands.includes(clean)) {
      setPreferredBrands([...preferredBrands, clean]);
      setNewBrandInput("");
    }
  };

  const handleRemoveBrand = (brandToRemove: string) => {
    setPreferredBrands(preferredBrands.filter((b) => b !== brandToRemove));
  };

  // Add Retailer Chip
  const handleAddRetailer = (e: React.FormEvent) => {
    e.preventDefault();
    const clean = newRetailerInput.trim();
    if (clean && !preferredRetailers.includes(clean)) {
      setPreferredRetailers([...preferredRetailers, clean]);
      setNewRetailerInput("");
    }
  };

  const handleRemoveRetailer = (retailerToRemove: string) => {
    setPreferredRetailers(preferredRetailers.filter((r) => r !== retailerToRemove));
  };

  // Toggle Shopping Priority
  const handleTogglePriority = (pId: string) => {
    if (selectedPriorities.includes(pId)) {
      if (selectedPriorities.length > 1) {
        setSelectedPriorities(selectedPriorities.filter((p) => p !== pId));
      }
    } else {
      setSelectedPriorities([...selectedPriorities, pId]);
    }
  };

  // Save Preference Profile
  const handleSaveProfile = async () => {
    try {
      setActionLoading(true);
      setFeedback(null);

      const minP = minPriceRupees ? parseInt(minPriceRupees, 10) * 100 : undefined;
      const maxP = maxPriceRupees ? parseInt(maxPriceRupees, 10) * 100 : undefined;

      const updated = await apiClient.updatePreferenceProfile({
        preferred_brands: preferredBrands,
        preferred_retailers: preferredRetailers,
        shopping_priorities: selectedPriorities,
        preferred_price_range: {
          min_paise: minP,
          max_paise: maxP,
        },
        personalization_enabled: personalizationEnabled,
      });

      setProfile(updated);
      setFeedback({
        type: "success",
        message: "Your shopping preferences have been securely saved.",
      });
    } catch (err: unknown) {
      const msg = err instanceof ApiClientError ? err.message : "Failed to save preferences.";
      setFeedback({ type: "error", message: msg });
    } finally {
      setActionLoading(false);
    }
  };

  // Create Recurring Intention
  const handleCreateIntention = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!intentionTitle.trim()) return;

    try {
      setActionLoading(true);
      setFeedback(null);
      const budgetPaise = intentionBudgetRupees ? parseInt(intentionBudgetRupees, 10) * 100 : undefined;

      const created = await apiClient.createRecurringIntention({
        title: intentionTitle.trim(),
        frequency: intentionFrequency,
        budget_paise: budgetPaise,
        notes: intentionNotes.trim() || undefined,
      });

      setIntentions([created, ...intentions]);
      setShowNewIntentionModal(false);
      setIntentionTitle("");
      setIntentionBudgetRupees("");
      setIntentionNotes("");
      setFeedback({
        type: "success",
        message: `Recurring intention "${created.title}" added successfully.`,
      });
    } catch (err: unknown) {
      const msg = err instanceof ApiClientError ? err.message : "Failed to create intention.";
      setFeedback({ type: "error", message: msg });
    } finally {
      setActionLoading(false);
    }
  };

  // Toggle Intention Status (Active/Paused)
  const handleToggleIntentionStatus = async (item: RecurringIntention) => {
    try {
      setActionLoading(true);
      const updated = await apiClient.toggleRecurringIntentionStatus(item.id, !item.is_active);
      setIntentions(intentions.map((i) => (i.id === item.id ? updated : i)));
      setFeedback({
        type: "success",
        message: `Intention "${item.title}" is now ${updated.is_active ? "Active" : "Paused"}.`,
      });
    } catch (err: unknown) {
      const msg = err instanceof ApiClientError ? err.message : "Failed to toggle intention status.";
      setFeedback({ type: "error", message: msg });
    } finally {
      setActionLoading(false);
    }
  };

  // Delete Intention
  const handleDeleteIntention = async (id: string, title: string) => {
    if (!window.confirm(`Delete recurring intention "${title}"?`)) return;
    try {
      setActionLoading(true);
      await apiClient.deleteRecurringIntention(id);
      setIntentions(intentions.filter((i) => i.id !== id));
      setFeedback({ type: "success", message: `Intention "${title}" deleted.` });
    } catch (err: unknown) {
      const msg = err instanceof ApiClientError ? err.message : "Failed to delete intention.";
      setFeedback({ type: "error", message: msg });
    } finally {
      setActionLoading(false);
    }
  };

  // Create Memory Item
  const handleCreateMemory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!memoryKey.trim() || !memorySummary.trim()) return;

    try {
      setActionLoading(true);
      setFeedback(null);
      const created = await apiClient.createIntentMemory({
        key: memoryKey.trim(),
        summary: memorySummary.trim(),
        memory_type: "NOTE",
        source: "CUSTOMER_STATED",
      });

      setMemories([created, ...memories]);
      setShowNewMemoryModal(false);
      setMemoryKey("");
      setMemorySummary("");
      setFeedback({ type: "success", message: "Memory note remembered." });
    } catch (err: unknown) {
      const msg = err instanceof ApiClientError ? err.message : "Failed to save memory.";
      setFeedback({ type: "error", message: msg });
    } finally {
      setActionLoading(false);
    }
  };

  // Delete Memory Item
  const handleDeleteMemory = async (id: string) => {
    try {
      setActionLoading(true);
      await apiClient.deleteIntentMemory(id);
      setMemories(memories.filter((m) => m.id !== id));
      setFeedback({ type: "success", message: "Memory removed." });
    } catch (err: unknown) {
      const msg = err instanceof ApiClientError ? err.message : "Failed to delete memory.";
      setFeedback({ type: "error", message: msg });
    } finally {
      setActionLoading(false);
    }
  };

  // Clear All Intent Data
  const handleClearAll = async () => {
    try {
      setActionLoading(true);
      setShowClearConfirm(false);
      const res = await apiClient.clearAllIntentMemories();
      setPreferredBrands([]);
      setPreferredRetailers([]);
      setSelectedPriorities(["BALANCED"]);
      setMinPriceRupees("");
      setMaxPriceRupees("");
      setIntentions([]);
      setMemories([]);
      setProfile(null);
      setFeedback({ type: "success", message: res.message });
    } catch (err: unknown) {
      const msg = err instanceof ApiClientError ? err.message : "Failed to clear shopping memories.";
      setFeedback({ type: "error", message: msg });
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <ProtectedRoute>
      <div className="container mx-auto px-4 py-8 sm:py-12 max-w-6xl">
        <div className="flex flex-col md:flex-row gap-8 items-start">
          <AccountNav />

          <main className="flex-1 w-full space-y-6">
            {/* Header Card */}
            <div className="rounded-2xl border bg-gradient-to-r from-amber-500/10 via-emerald-500/5 to-transparent p-6 sm:p-8">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="p-2 rounded-xl bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300">
                      <Sparkles className="h-5 w-5" />
                    </span>
                    <h1 className="text-2xl font-bold tracking-tight text-foreground">
                      Shopping Intent & Memory
                    </h1>
                  </div>
                  <p className="text-sm text-muted-foreground max-w-xl">
                    Teach BASKET your shopping tastes, recurring goals, and priority brands.
                    We use your memories strictly with your consent to personalize missions and substitutes.
                  </p>
                </div>

                {/* Consent Toggle Button */}
                <div className="flex items-center gap-3 bg-card border rounded-xl p-3 shadow-xs shrink-0">
                  <div className="text-right">
                    <div className="text-xs font-semibold text-foreground">
                      Personalization
                    </div>
                    <div className="text-[11px] text-muted-foreground">
                      {personalizationEnabled ? "Active & Personalized" : "Disabled (Neutral)"}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={handleToggleConsent}
                    disabled={actionLoading}
                    className="focus:outline-hidden"
                    title={personalizationEnabled ? "Disable Personalization" : "Enable Personalization"}
                  >
                    {personalizationEnabled ? (
                      <ToggleRight className="h-8 w-8 text-emerald-600 dark:text-emerald-400 cursor-pointer transition-transform hover:scale-105" />
                    ) : (
                      <ToggleLeft className="h-8 w-8 text-muted-foreground cursor-pointer transition-transform hover:scale-105" />
                    )}
                  </button>
                </div>
              </div>
            </div>

            {/* Notification Banner */}
            {feedback && (
              <div
                className={`p-4 rounded-xl border flex items-center justify-between gap-3 text-sm ${
                  feedback.type === "success"
                    ? "bg-emerald-50 border-emerald-200 text-emerald-800 dark:bg-emerald-950/40 dark:border-emerald-800 dark:text-emerald-300"
                    : "bg-red-50 border-red-200 text-red-800 dark:bg-red-950/40 dark:border-red-800 dark:text-red-300"
                }`}
              >
                <div className="flex items-center gap-2.5">
                  {feedback.type === "success" ? (
                    <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
                  ) : (
                    <AlertCircle className="h-4 w-4 shrink-0 text-red-600 dark:text-red-400" />
                  )}
                  <span>{feedback.message}</span>
                </div>
                <button
                  type="button"
                  onClick={() => setFeedback(null)}
                  className="text-xs font-medium hover:underline opacity-80"
                >
                  Dismiss
                </button>
              </div>
            )}

            {loading ? (
              <div className="p-12 text-center text-muted-foreground flex flex-col items-center gap-3">
                <Loader2 className="h-8 w-8 animate-spin text-amber-500" />
                <p className="text-sm font-medium">Loading your shopping intent memory...</p>
              </div>
            ) : (
              <>
                {/* 1. Shopping Preference Profile */}
                <Card className="border shadow-xs">
                  <CardHeader className="pb-4 border-b">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2.5">
                        <Sliders className="h-5 w-5 text-amber-600 dark:text-amber-400" />
                        <div>
                          <CardTitle className="text-base font-semibold">
                            Customer Shopping Preferences
                          </CardTitle>
                          <CardDescription className="text-xs">
                            Define your favorite brands, trusted retailers, and shopping priorities.
                          </CardDescription>
                        </div>
                      </div>
                      <Button
                        size="sm"
                        onClick={handleSaveProfile}
                        disabled={actionLoading}
                        className="bg-emerald-600 hover:bg-emerald-700 text-white font-medium gap-1.5"
                      >
                        {actionLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
                        Save Preferences
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent className="p-6 space-y-6">
                    {/* Preferred Brands */}
                    <div className="space-y-2.5">
                      <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                        <Tag className="h-3.5 w-3.5" /> Preferred Brands
                      </label>
                      <p className="text-xs text-muted-foreground">
                        Products from these brands will receive preference boosts in Basket Missions and Substitutes.
                      </p>
                      <div className="flex flex-wrap gap-2 items-center">
                        {preferredBrands.map((brand) => (
                          <span
                            key={brand}
                            className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-amber-50 border border-amber-200 text-amber-900 dark:bg-amber-950/50 dark:border-amber-800 dark:text-amber-300"
                          >
                            {brand}
                            <button
                              type="button"
                              onClick={() => handleRemoveBrand(brand)}
                              className="hover:text-red-600 focus:outline-hidden"
                            >
                              <X className="h-3 w-3" />
                            </button>
                          </span>
                        ))}
                      </div>
                      <form onSubmit={handleAddBrand} className="flex gap-2 max-w-sm">
                        <Input
                          placeholder="e.g. Sony, Apple, Nike"
                          value={newBrandInput}
                          onChange={(e) => setNewBrandInput(e.target.value)}
                          className="text-xs h-9"
                        />
                        <Button type="submit" variant="secondary" size="sm" className="h-9 text-xs">
                          Add Brand
                        </Button>
                      </form>
                    </div>

                    {/* Shopping Priorities */}
                    <div className="space-y-2.5 pt-4 border-t">
                      <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                        <Layers className="h-3.5 w-3.5" /> Shopping Priorities
                      </label>
                      <p className="text-xs text-muted-foreground">
                        Select which qualities guide BASKET when ranking listings and alternatives for you.
                      </p>
                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                        {SHOPPING_PRIORITIES.map((priority) => {
                          const isSelected = selectedPriorities.includes(priority.id);
                          return (
                            <button
                              type="button"
                              key={priority.id}
                              onClick={() => handleTogglePriority(priority.id)}
                              className={`text-left p-3.5 rounded-xl border transition-all ${
                                isSelected
                                  ? "border-amber-500 bg-amber-50/60 dark:bg-amber-950/30 text-amber-950 dark:text-amber-200 ring-1 ring-amber-500/40"
                                  : "border-zinc-200 dark:border-zinc-800 hover:border-zinc-300 text-muted-foreground"
                              }`}
                            >
                              <div className="flex items-center justify-between">
                                <span className="text-xs font-semibold text-foreground">
                                  {priority.label}
                                </span>
                                {isSelected ? (
                                  <CheckCircle2 className="h-4 w-4 text-amber-600 dark:text-amber-400" />
                                ) : null}
                              </div>
                              <p className="text-[11px] mt-1 opacity-80 leading-snug">
                                {priority.desc}
                              </p>
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    {/* Preferred Retailers */}
                    <div className="space-y-2.5 pt-4 border-t">
                      <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                        <Store className="h-3.5 w-3.5" /> Preferred Retailers
                      </label>
                      <p className="text-xs text-muted-foreground">
                        Specify stores you prefer to fulfill your basket orders.
                      </p>
                      <div className="flex flex-wrap gap-2 items-center">
                        {preferredRetailers.map((ret) => (
                          <span
                            key={ret}
                            className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-emerald-50 border border-emerald-200 text-emerald-900 dark:bg-emerald-950/50 dark:border-emerald-800 dark:text-emerald-300"
                          >
                            {ret}
                            <button
                              type="button"
                              onClick={() => handleRemoveRetailer(ret)}
                              className="hover:text-red-600 focus:outline-hidden"
                            >
                              <X className="h-3 w-3" />
                            </button>
                          </span>
                        ))}
                      </div>
                      <form onSubmit={handleAddRetailer} className="flex gap-2 max-w-sm">
                        <Input
                          placeholder="e.g. Basket Mart, Fresh Foods"
                          value={newRetailerInput}
                          onChange={(e) => setNewRetailerInput(e.target.value)}
                          className="text-xs h-9"
                        />
                        <Button type="submit" variant="secondary" size="sm" className="h-9 text-xs">
                          Add Store
                        </Button>
                      </form>
                    </div>

                    {/* Price Range */}
                    <div className="space-y-2.5 pt-4 border-t">
                      <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                        <DollarSign className="h-3.5 w-3.5" /> Target Price Range (₹)
                      </label>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-md">
                        <div>
                          <label className="text-[11px] text-muted-foreground mb-1 block">
                            Min Price (₹)
                          </label>
                          <Input
                            type="number"
                            min="0"
                            placeholder="0"
                            value={minPriceRupees}
                            onChange={(e) => setMinPriceRupees(e.target.value)}
                            className="text-xs h-9"
                          />
                        </div>
                        <div>
                          <label className="text-[11px] text-muted-foreground mb-1 block">
                            Max Price (₹)
                          </label>
                          <Input
                            type="number"
                            min="0"
                            placeholder="Optional"
                            value={maxPriceRupees}
                            onChange={(e) => setMaxPriceRupees(e.target.value)}
                            className="text-xs h-9"
                          />
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* 2. Recurring Shopping Intentions */}
                <Card className="border shadow-xs">
                  <CardHeader className="pb-4 border-b">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2.5">
                        <Calendar className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
                        <div>
                          <CardTitle className="text-base font-semibold">
                            Recurring Shopping Intentions
                          </CardTitle>
                          <CardDescription className="text-xs">
                            Repeating needs remembered for your shopping routines. We never auto-charge or auto-order.
                          </CardDescription>
                        </div>
                      </div>
                      <Button
                        size="sm"
                        onClick={() => setShowNewIntentionModal(true)}
                        className="bg-amber-500 hover:bg-amber-600 text-white font-medium gap-1.5"
                      >
                        <Plus className="h-3.5 w-3.5" />
                        Add Intention
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent className="p-6">
                    {/* Add Form Inline Modal */}
                    {showNewIntentionModal && (
                      <form
                        onSubmit={handleCreateIntention}
                        className="p-4 rounded-xl border bg-muted/30 mb-6 space-y-4"
                      >
                        <div className="flex items-center justify-between">
                          <h4 className="text-sm font-semibold text-foreground">
                            Add Recurring Shopping Goal
                          </h4>
                          <button
                            type="button"
                            onClick={() => setShowNewIntentionModal(false)}
                            className="text-muted-foreground hover:text-foreground"
                          >
                            <X className="h-4 w-4" />
                          </button>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                          <div>
                            <label className="text-xs font-medium mb-1 block text-muted-foreground">
                              Goal Title *
                            </label>
                            <Input
                              required
                              placeholder="e.g. Monthly Pantry Restock, Weekend Coffee Beans"
                              value={intentionTitle}
                              onChange={(e) => setIntentionTitle(e.target.value)}
                              className="text-xs h-9"
                            />
                          </div>

                          <div>
                            <label className="text-xs font-medium mb-1 block text-muted-foreground">
                              Frequency
                            </label>
                            <select
                              value={intentionFrequency}
                              onChange={(e) => setIntentionFrequency(e.target.value)}
                              className="w-full h-9 rounded-md border border-input bg-background px-3 py-1 text-xs shadow-xs focus-visible:outline-hidden focus-visible:ring-1 focus-visible:ring-ring"
                            >
                              {FREQUENCIES.map((f) => (
                                <option key={f.id} value={f.id}>
                                  {f.label}
                                </option>
                              ))}
                            </select>
                          </div>

                          <div>
                            <label className="text-xs font-medium mb-1 block text-muted-foreground">
                              Target Budget (₹)
                            </label>
                            <Input
                              type="number"
                              min="0"
                              placeholder="e.g. 2500"
                              value={intentionBudgetRupees}
                              onChange={(e) => setIntentionBudgetRupees(e.target.value)}
                              className="text-xs h-9"
                            />
                          </div>

                          <div>
                            <label className="text-xs font-medium mb-1 block text-muted-foreground">
                              Notes / Preferences
                            </label>
                            <Input
                              placeholder="e.g. Medium roast, whole beans only"
                              value={intentionNotes}
                              onChange={(e) => setIntentionNotes(e.target.value)}
                              className="text-xs h-9"
                            />
                          </div>
                        </div>

                        <div className="flex justify-end gap-2 pt-2">
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => setShowNewIntentionModal(false)}
                          >
                            Cancel
                          </Button>
                          <Button
                            type="submit"
                            size="sm"
                            disabled={actionLoading || !intentionTitle.trim()}
                            className="bg-emerald-600 hover:bg-emerald-700 text-white"
                          >
                            {actionLoading ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : null}
                            Save Goal
                          </Button>
                        </div>
                      </form>
                    )}

                    {intentions.length === 0 ? (
                      <div className="text-center py-8 text-muted-foreground space-y-2">
                        <Calendar className="h-8 w-8 mx-auto opacity-40 text-emerald-600" />
                        <p className="text-sm font-medium">No recurring intentions saved yet.</p>
                        <p className="text-xs text-muted-foreground max-w-sm mx-auto">
                          Create repeating goals for grocery staples, household refills, or seasonal shopping.
                        </p>
                      </div>
                    ) : (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {intentions.map((item) => (
                          <div
                            key={item.id}
                            className={`p-4 rounded-xl border transition-all ${
                              item.is_active
                                ? "bg-card border-zinc-200 dark:border-zinc-800"
                                : "bg-muted/30 border-dashed border-zinc-300 dark:border-zinc-800 opacity-75"
                            }`}
                          >
                            <div className="flex items-start justify-between gap-2">
                              <div>
                                <div className="flex items-center gap-2">
                                  <h4 className="font-semibold text-sm text-foreground">
                                    {item.title}
                                  </h4>
                                  <Badge
                                    variant={item.is_active ? "default" : "secondary"}
                                    className={`text-[10px] px-2 py-0.5 ${
                                      item.is_active
                                        ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border-emerald-200"
                                        : "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"
                                    }`}
                                  >
                                    {item.is_active ? "Active" : "Paused"}
                                  </Badge>
                                </div>
                                <div className="flex items-center gap-2 mt-1.5 text-xs text-muted-foreground">
                                  <span>{item.frequency}</span>
                                  {item.budget_paise ? (
                                    <>
                                      <span>•</span>
                                      <span className="font-medium text-foreground">
                                        Budget: {formatPrice(item.budget_paise)}
                                      </span>
                                    </>
                                  ) : null}
                                </div>
                                {item.notes && (
                                  <p className="text-xs text-muted-foreground mt-2 italic">
                                    &ldquo;{item.notes}&rdquo;
                                  </p>
                                )}
                              </div>
                            </div>

                            <div className="mt-4 pt-3 border-t flex items-center justify-between gap-2">
                              <Link
                                href={`/missions?title=${encodeURIComponent(item.title)}${
                                  item.budget_paise
                                    ? `&budget_rupees=${Math.round(item.budget_paise / 100)}`
                                    : ""
                                }`}
                                className="inline-flex items-center gap-1.5 text-xs font-semibold text-amber-600 dark:text-amber-400 hover:underline"
                              >
                                <Compass className="h-3.5 w-3.5" />
                                Plan Mission
                              </Link>

                              <div className="flex items-center gap-1">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleToggleIntentionStatus(item)}
                                  disabled={actionLoading}
                                  className="h-8 px-2 text-xs"
                                  title={item.is_active ? "Pause Intention" : "Resume Intention"}
                                >
                                  {item.is_active ? (
                                    <>
                                      <Pause className="h-3 w-3 mr-1 text-muted-foreground" /> Pause
                                    </>
                                  ) : (
                                    <>
                                      <Play className="h-3 w-3 mr-1 text-emerald-600" /> Resume
                                    </>
                                  )}
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleDeleteIntention(item.id, item.title)}
                                  disabled={actionLoading}
                                  className="h-8 px-2 text-xs text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950/30"
                                >
                                  <Trash2 className="h-3 w-3" />
                                </Button>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* 3. Explicit Memory Items */}
                <Card className="border shadow-xs">
                  <CardHeader className="pb-4 border-b">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2.5">
                        <Info className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                        <div>
                          <CardTitle className="text-base font-semibold">
                            Shopping Memory Notes
                          </CardTitle>
                          <CardDescription className="text-xs">
                            Explicit facts and notes remembered for tailoring suggestions.
                          </CardDescription>
                        </div>
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setShowNewMemoryModal(true)}
                        className="text-xs gap-1.5"
                      >
                        <Plus className="h-3.5 w-3.5" />
                        Add Note
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent className="p-6">
                    {/* Add Form Inline Modal */}
                    {showNewMemoryModal && (
                      <form
                        onSubmit={handleCreateMemory}
                        className="p-4 rounded-xl border bg-muted/30 mb-6 space-y-4"
                      >
                        <div className="flex items-center justify-between">
                          <h4 className="text-sm font-semibold text-foreground">
                            Remember a Shopping Note
                          </h4>
                          <button
                            type="button"
                            onClick={() => setShowNewMemoryModal(false)}
                            className="text-muted-foreground hover:text-foreground"
                          >
                            <X className="h-4 w-4" />
                          </button>
                        </div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                          <div>
                            <label className="text-xs font-medium mb-1 block text-muted-foreground">
                              Topic / Keyword *
                            </label>
                            <Input
                              required
                              placeholder="e.g. coffee_roast, shoe_size"
                              value={memoryKey}
                              onChange={(e) => setMemoryKey(e.target.value)}
                              className="text-xs h-9"
                            />
                          </div>
                          <div>
                            <label className="text-xs font-medium mb-1 block text-muted-foreground">
                              Summary Note *
                            </label>
                            <Input
                              required
                              placeholder="e.g. Always prefer whole bean dark roast"
                              value={memorySummary}
                              onChange={(e) => setMemorySummary(e.target.value)}
                              className="text-xs h-9"
                            />
                          </div>
                        </div>
                        <div className="flex justify-end gap-2 pt-2">
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => setShowNewMemoryModal(false)}
                          >
                            Cancel
                          </Button>
                          <Button
                            type="submit"
                            size="sm"
                            disabled={actionLoading || !memoryKey.trim() || !memorySummary.trim()}
                            className="bg-emerald-600 hover:bg-emerald-700 text-white"
                          >
                            {actionLoading ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : null}
                            Remember Note
                          </Button>
                        </div>
                      </form>
                    )}

                    {memories.length === 0 ? (
                      <p className="text-xs text-muted-foreground text-center py-6">
                        No shopping memory notes recorded.
                      </p>
                    ) : (
                      <div className="divide-y border rounded-xl overflow-hidden">
                        {memories.map((mem) => (
                          <div
                            key={mem.id}
                            className="p-3.5 flex items-center justify-between gap-4 hover:bg-muted/20 transition-colors"
                          >
                            <div className="space-y-1">
                              <div className="flex items-center gap-2">
                                <span className="font-semibold text-xs text-foreground">
                                  {mem.key}
                                </span>
                                <Badge variant="outline" className="text-[10px] py-0 px-1.5">
                                  {mem.source}
                                </Badge>
                              </div>
                              <p className="text-xs text-muted-foreground">
                                {mem.summary}
                              </p>
                            </div>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDeleteMemory(mem.id)}
                              disabled={actionLoading}
                              className="h-8 w-8 p-0 text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950/30"
                              title="Delete note"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* 4. Privacy & Safety Guarantee + Clear All Data */}
                <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-card p-6 space-y-4">
                  <div className="flex items-start gap-3">
                    <ShieldCheck className="h-5 w-5 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
                    <div className="space-y-1">
                      <h4 className="text-sm font-semibold text-foreground">
                        Privacy and Customer Isolation Guaranteed
                      </h4>
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        Your intent memory is private to your account and never shared with other customers,
                        third-party trackers, or unapproved retailers. BASKET never uses memory to place unapproved orders
                        or charge payments. You remain in complete control of your data at all times.
                      </p>
                    </div>
                  </div>

                  <div className="pt-4 border-t flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div>
                      <h5 className="text-xs font-semibold text-foreground">
                        Clear All Shopping Memories
                      </h5>
                      <p className="text-[11px] text-muted-foreground">
                        Permanently remove all saved brands, priorities, recurring intentions, and notes.
                      </p>
                    </div>

                    {showClearConfirm ? (
                      <div className="flex items-center gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setShowClearConfirm(false)}
                          className="text-xs"
                        >
                          Cancel
                        </Button>
                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={handleClearAll}
                          disabled={actionLoading}
                          className="text-xs"
                        >
                          {actionLoading ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : null}
                          Yes, Delete Everything
                        </Button>
                      </div>
                    ) : (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setShowClearConfirm(true)}
                        className="text-xs text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950/30 border-red-200 dark:border-red-900"
                      >
                        <Trash2 className="h-3.5 w-3.5 mr-1" />
                        Clear All Memories
                      </Button>
                    )}
                  </div>
                </div>
              </>
            )}
          </main>
        </div>
      </div>
    </ProtectedRoute>
  );
}
