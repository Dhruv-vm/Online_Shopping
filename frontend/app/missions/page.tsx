"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Compass,
  Target,
  Sparkles,
  Plus,
  ArrowRight,
  Clock,
  Layers,
  IndianRupee,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  Lock,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { apiClient } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/auth-context";
import type { MissionSummary, Category } from "@/types";

interface Template {
  title: string;
  budgetInr: number;
  peopleCount: number;
  preferences: string[];
  description: string;
  categorySlug?: string;
}

const TEMPLATES: Template[] = [
  {
    title: "Set up a complete kitchen under ₹15,000",
    budgetInr: 15000,
    peopleCount: 2,
    preferences: ["durable", "stainless steel", "non-stick"],
    description: "Cookware, storage containers, prep knives, and essential kitchen tools for daily cooking.",
    categorySlug: "home-kitchen",
  },
  {
    title: "New apartment essentials checklist",
    budgetInr: 25000,
    peopleCount: 2,
    preferences: ["essential", "modern", "reliable"],
    description: "Basic furnishings, kitchen essentials, cleaning supplies, and linen for a fresh move-in.",
    categorySlug: "home-kitchen",
  },
  {
    title: "Home gym setup under ₹10,000",
    budgetInr: 10000,
    peopleCount: 1,
    preferences: ["fitness", "yoga", "strength"],
    description: "Resistance bands, yoga mat, dumbbells, and activewear for home workouts.",
    categorySlug: "sports-fitness",
  },
  {
    title: "Newborn baby care essentials",
    budgetInr: 12000,
    peopleCount: 1,
    preferences: ["gentle", "cotton", "hypoallergenic"],
    description: "Feeding bottles, soft swaddles, skincare, and daily nursery essentials.",
    categorySlug: "baby-care",
  },
  {
    title: "Work-from-home productivity desk",
    budgetInr: 20000,
    peopleCount: 1,
    preferences: ["ergonomic", "minimalist", "cable management"],
    description: "Desk accessories, laptop stand, audio headset, and ergonomic support for remote work.",
    categorySlug: "electronics",
  },
  {
    title: "Family monthly grocery restock",
    budgetInr: 6000,
    peopleCount: 4,
    preferences: ["organic", "staples", "healthy"],
    description: "Pantry staples, pulses, cooking oils, organic spices, and healthy breakfast grains.",
    categorySlug: "grocery-food",
  },
];

export default function MissionsPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();

  const [categories, setCategories] = useState<Category[]>([]);
  const [missions, setMissions] = useState<MissionSummary[]>([]);
  const [loadingMissions, setLoadingMissions] = useState(false);

  // Form State
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [budgetInr, setBudgetInr] = useState("15000");
  const [peopleCount, setPeopleCount] = useState(2);
  const [selectedCategory, setSelectedCategory] = useState<string>("");
  const [preferencesStr, setPreferencesStr] = useState("");
  const [excludedBrandsStr, setExcludedBrandsStr] = useState("");

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Load initial categories
  useEffect(() => {
    let mounted = true;
    apiClient
      .getCategories()
      .then((cats) => {
        if (mounted) setCategories(cats);
      })
      .catch(() => {});
    return () => {
      mounted = false;
    };
  }, []);

  // Load saved missions when authenticated
  useEffect(() => {
    if (!isAuthenticated) return;
    let mounted = true;
    setLoadingMissions(true);
    apiClient
      .getMissions()
      .then((data) => {
        if (mounted) setMissions(data);
      })
      .catch(() => {})
      .finally(() => {
        if (mounted) setLoadingMissions(false);
      });
    return () => {
      mounted = false;
    };
  }, [isAuthenticated]);

  const applyTemplate = (t: Template) => {
    setTitle(t.title);
    setDescription(t.description);
    setBudgetInr(t.budgetInr.toString());
    setPeopleCount(t.peopleCount);
    setPreferencesStr(t.preferences.join(", "));

    if (t.categorySlug && categories.length > 0) {
      const matched = categories.find((c) => c.slug === t.categorySlug);
      if (matched) setSelectedCategory(matched.id);
    }
  };

  const handleCreateMission = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    if (!isAuthenticated) {
      router.push(`/auth/login?redirect=${encodeURIComponent("/missions")}`);
      return;
    }

    const budgetNum = parseFloat(budgetInr);
    if (isNaN(budgetNum) || budgetNum <= 0) {
      setErrorMsg("Please enter a valid budget in Rupees.");
      return;
    }

    if (!title.trim()) {
      setErrorMsg("Please specify what goal or mission you want to achieve.");
      return;
    }

    setIsSubmitting(true);
    try {
      const budgetPaise = Math.round(budgetNum * 100);
      const preferences = preferencesStr
        .split(",")
        .map((p) => p.trim())
        .filter(Boolean);
      const excludedBrands = excludedBrandsStr
        .split(",")
        .map((b) => b.trim())
        .filter(Boolean);

      const mission = await apiClient.createMission({
        title: title.trim(),
        description: description.trim() || undefined,
        budget_paise: budgetPaise,
        people_count: peopleCount,
        category_id: selectedCategory || undefined,
        preferences,
        excluded_brands: excludedBrands,
      });

      router.push(`/missions/${mission.id}`);
    } catch (err: unknown) {
      const apiErr = err as { message?: string };
      setErrorMsg(apiErr.message || "Failed to create mission plan. Please try again.");
      setIsSubmitting(false);
    }
  };

  return (
    <div className="container mx-auto space-y-12 px-4 py-8 sm:px-6 max-w-6xl">
      {/* Hero Header */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-slate-900 via-emerald-950 to-slate-900 px-6 py-10 sm:px-10 sm:py-14 text-white shadow-xl">
        <div className="relative z-10 max-w-3xl space-y-4">
          <div className="inline-flex items-center gap-2 rounded-full bg-emerald-500/20 px-3 py-1 text-xs font-semibold text-emerald-300 border border-emerald-400/30">
            <Compass className="h-4 w-4" />
            <span>Basket Mission • Guided Shopping</span>
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl sm:leading-tight">
            Shop by Goal, not individual items.
          </h1>
          <p className="text-sm sm:text-base text-emerald-100/90 leading-relaxed">
            Describe what you need to achieve — from setting up a kitchen under ₹15,000 to preparing for a new baby. We assemble a complete shopping plan using genuine marketplace inventory, live pricing, and verified retailer stock.
          </p>
        </div>
        <div className="absolute -right-20 -bottom-20 h-80 w-80 rounded-full bg-emerald-500/20 blur-3xl pointer-events-none" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Creation Wizard */}
        <div className="lg:col-span-7 space-y-6">
          <Card className="border shadow-sm">
            <CardHeader className="pb-4">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-xl font-bold flex items-center gap-2">
                    <Target className="h-5 w-5 text-emerald-600" />
                    Create Your Shopping Plan
                  </CardTitle>
                  <CardDescription className="text-xs sm:text-sm">
                    Enter your budget and goal, or pick a quick-start template below.
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Inspiration Template Chips */}
              <div className="space-y-2">
                <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                  <Sparkles className="h-3.5 w-3.5 text-amber-500" />
                  Quick Inspiration Templates
                </label>
                <div className="flex flex-wrap gap-2">
                  {TEMPLATES.map((t, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => applyTemplate(t)}
                      className="text-xs px-3 py-1.5 rounded-full border bg-muted/40 hover:bg-emerald-50 dark:hover:bg-emerald-950/40 hover:border-emerald-500/50 hover:text-emerald-700 transition-colors text-left"
                    >
                      {t.title.split(" under ")[0]} • ₹{t.budgetInr.toLocaleString("en-IN")}
                    </button>
                  ))}
                </div>
              </div>

              {/* Form */}
              <form onSubmit={handleCreateMission} className="space-y-4">
                <div className="space-y-1.5">
                  <label htmlFor="mission-title" className="text-xs font-semibold text-foreground">
                    What is your shopping goal? <span className="text-destructive">*</span>
                  </label>
                  <Input
                    id="mission-title"
                    type="text"
                    placeholder="e.g. Set up a kitchen under ₹15,000"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    required
                    className="h-10 text-sm"
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label htmlFor="mission-budget" className="text-xs font-semibold text-foreground flex items-center gap-1">
                      <IndianRupee className="h-3.5 w-3.5 text-emerald-600" />
                      Budget in Rupees (₹) <span className="text-destructive">*</span>
                    </label>
                    <Input
                      id="mission-budget"
                      type="number"
                      min="500"
                      step="100"
                      placeholder="15000"
                      value={budgetInr}
                      onChange={(e) => setBudgetInr(e.target.value)}
                      required
                      className="h-10 font-mono text-sm"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label htmlFor="mission-people" className="text-xs font-semibold text-foreground">
                      Household / Users Count
                    </label>
                    <select
                      id="mission-people"
                      value={peopleCount}
                      onChange={(e) => setPeopleCount(parseInt(e.target.value, 10))}
                      className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-xs focus:outline-hidden focus:ring-1 focus:ring-ring"
                    >
                      <option value={1}>1 Person (Individual)</option>
                      <option value={2}>2 People (Couple / Roommates)</option>
                      <option value={3}>3 People (Small Family)</option>
                      <option value={4}>4 People (Standard Family)</option>
                      <option value={5}>5+ People (Large Household)</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label htmlFor="mission-cat" className="text-xs font-semibold text-foreground">
                      Department / Category (Optional)
                    </label>
                    <select
                      id="mission-cat"
                      value={selectedCategory}
                      onChange={(e) => setSelectedCategory(e.target.value)}
                      className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-xs focus:outline-hidden focus:ring-1 focus:ring-ring"
                    >
                      <option value="">All Categories (Auto-Detect)</option>
                      {categories.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="space-y-1.5">
                    <label htmlFor="mission-prefs" className="text-xs font-semibold text-foreground">
                      Preferences / Keywords (Optional)
                    </label>
                    <Input
                      id="mission-prefs"
                      type="text"
                      placeholder="e.g. durable, non-stick, organic"
                      value={preferencesStr}
                      onChange={(e) => setPreferencesStr(e.target.value)}
                      className="h-10 text-sm"
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label htmlFor="mission-excl" className="text-xs font-semibold text-foreground">
                    Excluded Brands (Optional, comma-separated)
                  </label>
                  <Input
                    id="mission-excl"
                    type="text"
                    placeholder="e.g. GenericBrandA, CheapCo"
                    value={excludedBrandsStr}
                    onChange={(e) => setExcludedBrandsStr(e.target.value)}
                    className="h-10 text-sm"
                  />
                </div>

                {errorMsg && (
                  <div className="p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-xs flex items-start gap-2">
                    <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                    <span>{errorMsg}</span>
                  </div>
                )}

                <div className="pt-2">
                  <Button
                    type="submit"
                    disabled={isSubmitting}
                    className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-semibold h-11 text-sm shadow-md"
                  >
                    {isSubmitting ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin mr-2" />
                        Analyzing Marketplace & Curating Plan...
                      </>
                    ) : (
                      <>
                        <Target className="h-4 w-4 mr-2" />
                        Generate Mission Plan
                      </>
                    )}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </div>

        {/* Saved Missions Sidebar */}
        <div className="lg:col-span-5 space-y-6">
          <Card className="border shadow-sm">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg font-bold flex items-center gap-2">
                  <Clock className="h-4 w-4 text-emerald-600" />
                  Your Saved Missions
                </CardTitle>
                {isAuthenticated && missions.length > 0 && (
                  <Badge variant="outline" className="text-xs">
                    {missions.length} plans
                  </Badge>
                )}
              </div>
              <CardDescription className="text-xs">
                Review, track, and update your existing shopping missions.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {!isAuthenticated ? (
                <div className="rounded-xl border border-dashed p-6 text-center space-y-3">
                  <Lock className="h-8 w-8 text-muted-foreground mx-auto" />
                  <p className="text-xs text-muted-foreground">
                    Sign in to your customer account to save and track your personal missions.
                  </p>
                  <Link href={`/auth/login?redirect=${encodeURIComponent("/missions")}`}>
                    <Button variant="outline" size="sm" className="text-xs">
                      Sign In to Account
                    </Button>
                  </Link>
                </div>
              ) : loadingMissions ? (
                <div className="p-8 text-center text-xs text-muted-foreground flex items-center justify-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading your missions...
                </div>
              ) : missions.length === 0 ? (
                <div className="rounded-xl border border-dashed p-6 text-center space-y-2">
                  <Compass className="h-8 w-8 text-muted-foreground/60 mx-auto" />
                  <p className="text-xs font-semibold text-foreground">No missions created yet</p>
                  <p className="text-xs text-muted-foreground">
                    Fill out the form on the left or click a template to create your first goal-based plan.
                  </p>
                </div>
              ) : (
                <div className="space-y-3 max-h-[500px] overflow-y-auto pr-1">
                  {missions.map((m) => {
                    const budgetInrVal = (m.budget_paise / 100).toLocaleString("en-IN");
                    const costInrVal = (m.total_cost_paise / 100).toLocaleString("en-IN");
                    const remInrVal = (m.remaining_budget_paise / 100).toLocaleString("en-IN");

                    return (
                      <Link
                        key={m.id}
                        href={`/missions/${m.id}`}
                        className="block p-3.5 rounded-xl border bg-card hover:border-emerald-500/50 hover:shadow-xs transition-all space-y-2 group"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <h4 className="text-xs font-bold text-foreground group-hover:text-emerald-700 transition-colors line-clamp-1">
                            {m.title}
                          </h4>
                          <Badge
                            variant={m.status === "ACTIVE" ? "default" : "secondary"}
                            className="text-[10px] uppercase font-semibold shrink-0"
                          >
                            {m.status}
                          </Badge>
                        </div>

                        <div className="grid grid-cols-2 gap-2 text-[11px] text-muted-foreground bg-muted/40 p-2 rounded-lg">
                          <div>
                            <span className="block text-[10px] uppercase tracking-wider text-muted-foreground/80">
                              Budget
                            </span>
                            <span className="font-semibold text-foreground">₹{budgetInrVal}</span>
                          </div>
                          <div>
                            <span className="block text-[10px] uppercase tracking-wider text-muted-foreground/80">
                              Plan Total
                            </span>
                            <span className="font-semibold text-foreground">₹{costInrVal}</span>
                          </div>
                        </div>

                        <div className="flex items-center justify-between text-[11px] pt-1">
                          <span className="text-muted-foreground flex items-center gap-1">
                            <Layers className="h-3 w-3" />
                            {m.items_count} products
                          </span>
                          {m.is_over_budget ? (
                            <span className="text-amber-600 dark:text-amber-400 font-semibold flex items-center gap-1">
                              <AlertTriangle className="h-3 w-3" />
                              Over Budget
                            </span>
                          ) : (
                            <span className="text-emerald-600 dark:text-emerald-400 font-semibold flex items-center gap-1">
                              <CheckCircle2 className="h-3 w-3" />
                              ₹{remInrVal} left
                            </span>
                          )}
                        </div>
                      </Link>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Value Props Card */}
          <Card className="border bg-muted/20">
            <CardContent className="p-4 space-y-3 text-xs">
              <h4 className="font-bold text-foreground flex items-center gap-1.5">
                <Sparkles className="h-3.5 w-3.5 text-emerald-600" />
                How Basket Mission Works
              </h4>
              <ul className="space-y-2 text-muted-foreground">
                <li className="flex items-start gap-2">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-600 shrink-0 mt-1.5" />
                  <span><strong>Real Inventory Only:</strong> Matches items exclusively against verified retailers with in-stock items.</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-600 shrink-0 mt-1.5" />
                  <span><strong>Thematic Grouping:</strong> Automatically divides your goal into logical product categories.</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-600 shrink-0 mt-1.5" />
                  <span><strong>Budget Guardrails:</strong> Optimizes price-to-utility and flags overages transparently.</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-600 shrink-0 mt-1.5" />
                  <span><strong>Direct Checkout:</strong> Add all selected mission items to your universal shopping basket in one click.</span>
                </li>
              </ul>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
