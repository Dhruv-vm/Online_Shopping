"use client";

import { useEffect, useState } from "react";
import {
  Award,
  Box,
  CheckCircle2,
  Clock,
  ExternalLink,
  FileCheck2,
  FileText,
  Info,
  Layers,
  ShieldCheck,
  Store,
  Truck,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { apiClient } from "@/lib/api/client";
import type { PublicProductPassport } from "@/types";

interface ProductPassportSectionProps {
  productIdOrSlug: string;
  selectedListingId?: string | null;
}

export function ProductPassportSection({
  productIdOrSlug,
  selectedListingId,
}: ProductPassportSectionProps) {
  const [passport, setPassport] = useState<PublicProductPassport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"specifications" | "claims" | "seller">("specifications");

  useEffect(() => {
    let isMounted = true;
    async function loadPassport() {
      setIsLoading(true);
      setError(null);
      try {
        const data = await apiClient.getProductPassport(
          productIdOrSlug,
          selectedListingId || undefined
        );
        if (isMounted) {
          setPassport(data);
        }
      } catch (err: unknown) {
        if (isMounted) {
          setError(err instanceof Error ? err.message : "Failed to load passport");
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    loadPassport();
    return () => {
      isMounted = false;
    };
  }, [productIdOrSlug, selectedListingId]);

  if (isLoading) {
    return (
      <div className="rounded-2xl border bg-card p-6 shadow-xs animate-pulse space-y-4">
        <div className="h-6 w-48 bg-muted rounded" />
        <div className="h-20 bg-muted/50 rounded-xl" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="h-16 bg-muted/40 rounded-lg" />
          <div className="h-16 bg-muted/40 rounded-lg" />
          <div className="h-16 bg-muted/40 rounded-lg" />
          <div className="h-16 bg-muted/40 rounded-lg" />
        </div>
      </div>
    );
  }

  if (error || !passport) {
    return (
      <div className="rounded-2xl border border-dashed p-6 text-center text-sm text-muted-foreground bg-muted/10">
        <Info className="h-5 w-5 mx-auto mb-2 text-muted-foreground/80" />
        <p className="font-medium text-foreground">Product Passport not available</p>
        <p className="text-xs mt-1">Detailed specifications and claims could not be loaded at this time.</p>
      </div>
    );
  }

  const hasCanonicalSpecs =
    passport.manufacturer ||
    passport.country_of_origin ||
    passport.model_number ||
    passport.gtin_ean_upc ||
    (passport.materials && passport.materials.length > 0) ||
    Object.keys(passport.technical_specs || {}).length > 0 ||
    passport.warranty_info;

  const allClaims = [
    ...(passport.claims || []),
    ...(passport.listing_passport?.claims || []),
  ];

  return (
    <Card className="rounded-2xl border border-emerald-600/20 bg-gradient-to-b from-card to-muted/20 overflow-hidden shadow-xs">
      <div className="border-b bg-muted/30 px-6 py-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-emerald-600/10 text-emerald-600 dark:text-emerald-400">
            <FileCheck2 className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-extrabold text-base text-foreground tracking-tight">
                Product Passport
              </h3>
              <Badge variant="outline" className="text-emerald-700 dark:text-emerald-300 border-emerald-600/40 bg-emerald-50 dark:bg-emerald-950/40 text-[10px] uppercase font-bold tracking-wider">
                Phase 2D Transparency
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              Traceable product specifications, verified compliance claims, and seller-specific attributes.
            </p>
          </div>
        </div>

        {/* Tab Controls */}
        <div className="flex items-center bg-muted/60 p-1 rounded-xl text-xs font-medium">
          <button
            onClick={() => setActiveTab("specifications")}
            className={`px-3 py-1.5 rounded-lg transition-all ${
              activeTab === "specifications"
                ? "bg-background text-foreground shadow-xs font-semibold"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            Specifications
          </button>
          <button
            onClick={() => setActiveTab("claims")}
            className={`px-3 py-1.5 rounded-lg transition-all flex items-center gap-1.5 ${
              activeTab === "claims"
                ? "bg-background text-foreground shadow-xs font-semibold"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            Claims & Proof
            {allClaims.length > 0 && (
              <span className="px-1.5 py-0.2 bg-emerald-600/10 text-emerald-700 dark:text-emerald-300 rounded-full text-[10px] font-bold">
                {allClaims.length}
              </span>
            )}
          </button>
          {passport.listing_passport && (
            <button
              onClick={() => setActiveTab("seller")}
              className={`px-3 py-1.5 rounded-lg transition-all ${
                activeTab === "seller"
                  ? "bg-background text-foreground shadow-xs font-semibold"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Seller Details
            </button>
          )}
        </div>
      </div>

      <CardContent className="p-6">
        {/* TAB 1: SPECIFICATIONS */}
        {activeTab === "specifications" && (
          <div className="space-y-6">
            {!hasCanonicalSpecs ? (
              <div className="text-center py-8 px-4 rounded-xl border border-dashed bg-muted/10 text-muted-foreground text-xs">
                <Box className="h-8 w-8 mx-auto mb-2 text-muted-foreground/60" />
                <p className="font-semibold text-foreground text-sm">
                  Passport Awaiting Verification
                </p>
                <p className="max-w-md mx-auto mt-1">
                  Canonical manufacturer facts and lab certificates are currently undergoing moderation for {passport.product_name}.
                </p>
              </div>
            ) : (
              <>
                {/* Core Identity Facts */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="p-3 rounded-xl border bg-card/60">
                    <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider block">
                      Manufacturer
                    </span>
                    <span className="text-sm font-bold text-foreground mt-0.5 block truncate">
                      {passport.manufacturer || passport.brand || "Verified Brand"}
                    </span>
                  </div>

                  <div className="p-3 rounded-xl border bg-card/60">
                    <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider block">
                      Origin
                    </span>
                    <span className="text-sm font-bold text-foreground mt-0.5 block truncate">
                      {passport.country_of_origin || "India"}
                    </span>
                  </div>

                  <div className="p-3 rounded-xl border bg-card/60">
                    <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider block">
                      Model / SKU
                    </span>
                    <span className="text-sm font-bold text-foreground mt-0.5 block truncate">
                      {passport.model_number || "Standard"}
                    </span>
                  </div>

                  <div className="p-3 rounded-xl border bg-card/60">
                    <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider block">
                      GTIN / UPC / EAN
                    </span>
                    <span className="text-sm font-bold text-foreground mt-0.5 block truncate">
                      {passport.gtin_ean_upc || "Verified EAN"}
                    </span>
                  </div>
                </div>

                {/* Technical Specifications Grid */}
                {passport.technical_specs && Object.keys(passport.technical_specs).length > 0 && (
                  <div className="space-y-2">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                      <Layers className="h-3.5 w-3.5 text-emerald-600" />
                      Technical Specifications
                    </h4>
                    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
                      {Object.entries(passport.technical_specs).map(([key, val]) => (
                        <div
                          key={key}
                          className="flex items-center justify-between p-2.5 rounded-lg border bg-muted/20 text-xs"
                        >
                          <span className="text-muted-foreground capitalize">
                            {key.replace(/_/g, " ")}:
                          </span>
                          <span className="font-semibold text-foreground">
                            {typeof val === "object" ? JSON.stringify(val) : String(val)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Materials & Package Contents */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {passport.materials && passport.materials.length > 0 && (
                    <div className="p-3.5 rounded-xl border bg-muted/10 space-y-2">
                      <span className="text-xs font-bold text-foreground block">
                        Composition & Materials
                      </span>
                      <div className="flex flex-wrap gap-1.5">
                        {passport.materials.map((m, idx) => (
                          <Badge key={idx} variant="secondary" className="text-xs font-medium">
                            {typeof m === "string" ? m : JSON.stringify(m)}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}

                  {passport.package_contents && passport.package_contents.length > 0 && (
                    <div className="p-3.5 rounded-xl border bg-muted/10 space-y-2">
                      <span className="text-xs font-bold text-foreground block">
                        In The Box
                      </span>
                      <ul className="text-xs text-muted-foreground space-y-1 list-disc list-inside">
                        {passport.package_contents.map((item, idx) => (
                          <li key={idx} className="truncate">
                            {item}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                {/* Warranty & Safety Instructions */}
                {(passport.warranty_info || passport.safety_instructions) && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs pt-1">
                    {passport.warranty_info && (
                      <div className="p-3 rounded-xl border border-emerald-600/20 bg-emerald-600/5">
                        <span className="font-bold text-emerald-950 dark:text-emerald-200 block mb-1 flex items-center gap-1.5">
                          <ShieldCheck className="h-4 w-4 text-emerald-600" />
                          Manufacturer Warranty
                        </span>
                        <p className="text-muted-foreground leading-relaxed">
                          {passport.warranty_info}
                        </p>
                      </div>
                    )}
                    {passport.safety_instructions && (
                      <div className="p-3 rounded-xl border border-amber-600/20 bg-amber-600/5">
                        <span className="font-bold text-amber-950 dark:text-amber-200 block mb-1 flex items-center gap-1.5">
                          <Info className="h-4 w-4 text-amber-600" />
                          Safety & Handling
                        </span>
                        <p className="text-muted-foreground leading-relaxed">
                          {passport.safety_instructions}
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* TAB 2: CLAIMS & PROOF */}
        {activeTab === "claims" && (
          <div className="space-y-4">
            {allClaims.length === 0 ? (
              <div className="text-center py-8 px-4 rounded-xl border border-dashed bg-muted/10 text-muted-foreground text-xs">
                <FileText className="h-8 w-8 mx-auto mb-2 text-muted-foreground/60" />
                <p className="font-semibold text-foreground text-sm">
                  No Verified Claims Submitted
                </p>
                <p className="max-w-md mx-auto mt-1">
                  Retailer certifications or compliance declarations have not been registered for this listing yet.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="flex items-center justify-between text-xs text-muted-foreground pb-1">
                  <span>Transparent Claim Auditing</span>
                  <span>{allClaims.filter((c) => c.review_status === "VERIFIED").length} of {allClaims.length} verified</span>
                </div>

                <div className="grid grid-cols-1 gap-2.5">
                  {allClaims.map((claim) => {
                    const isVerified = claim.review_status === "VERIFIED";
                    const isPending = claim.review_status === "PENDING";

                    return (
                      <div
                        key={claim.id}
                        className={`p-3.5 rounded-xl border transition-all ${
                          isVerified
                            ? "border-emerald-600/30 bg-emerald-600/5"
                            : isPending
                            ? "border-amber-600/30 bg-amber-600/5"
                            : "border-muted bg-muted/20"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="space-y-1">
                            <div className="flex items-center gap-2">
                              <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                                {claim.claim_type} • {claim.claim_key.replace(/_/g, " ")}
                              </span>
                              {claim.claim_scope === "LISTING" && (
                                <Badge variant="outline" className="text-[9px] px-1.5 py-0 h-4">
                                  Seller Specific
                                </Badge>
                              )}
                            </div>
                            <p className="text-sm font-semibold text-foreground">
                              {claim.claim_value}
                            </p>
                          </div>

                          <div className="shrink-0 flex flex-col items-end gap-1.5">
                            {isVerified ? (
                              <Badge className="bg-emerald-600 text-white hover:bg-emerald-700 flex items-center gap-1 text-[11px]">
                                <CheckCircle2 className="h-3 w-3" />
                                Verified
                              </Badge>
                            ) : isPending ? (
                              <Badge variant="outline" className="text-amber-700 dark:text-amber-300 border-amber-600/40 bg-amber-50 dark:bg-amber-950/40 flex items-center gap-1 text-[11px]">
                                <Clock className="h-3 w-3" />
                                Awaiting Review
                              </Badge>
                            ) : (
                              <Badge variant="secondary" className="text-[11px]">
                                Unverified
                              </Badge>
                            )}

                            {claim.evidence_url && (
                              <a
                                href={claim.evidence_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-[11px] font-medium text-emerald-700 dark:text-emerald-400 hover:underline flex items-center gap-1"
                              >
                                View Evidence
                                <ExternalLink className="h-3 w-3" />
                              </a>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 3: SELLER DETAILS */}
        {activeTab === "seller" && passport.listing_passport && (
          <div className="space-y-4">
            <div className="p-4 rounded-xl border bg-card space-y-4">
              <div className="flex items-center justify-between pb-3 border-b">
                <div className="flex items-center gap-2">
                  <Store className="h-4 w-4 text-emerald-600" />
                  <span className="text-sm font-bold text-foreground">
                    {passport.listing_passport.retailer_name}
                  </span>
                </div>
                <Badge
                  variant={
                    passport.listing_passport.item_condition === "NEW" ? "default" : "secondary"
                  }
                  className="font-bold text-xs"
                >
                  Condition: {passport.listing_passport.item_condition}
                </Badge>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                {passport.listing_passport.seller_warranty && (
                  <div className="p-3 rounded-lg border bg-muted/20 space-y-1">
                    <span className="font-semibold text-foreground flex items-center gap-1">
                      <Award className="h-3.5 w-3.5 text-emerald-600" />
                      Seller Warranty Terms
                    </span>
                    <p className="text-muted-foreground leading-relaxed">
                      {passport.listing_passport.seller_warranty}
                    </p>
                  </div>
                )}

                {passport.listing_passport.packaging_notes && (
                  <div className="p-3 rounded-lg border bg-muted/20 space-y-1">
                    <span className="font-semibold text-foreground flex items-center gap-1">
                      <Box className="h-3.5 w-3.5 text-emerald-600" />
                      Packaging & Handling
                    </span>
                    <p className="text-muted-foreground leading-relaxed">
                      {passport.listing_passport.packaging_notes}
                    </p>
                  </div>
                )}
              </div>

              {passport.listing_passport.fulfillment_notes && (
                <div className="p-3 rounded-lg border border-dashed text-xs text-muted-foreground flex items-center gap-2">
                  <Truck className="h-4 w-4 text-emerald-600 shrink-0" />
                  <span>{passport.listing_passport.fulfillment_notes}</span>
                </div>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
