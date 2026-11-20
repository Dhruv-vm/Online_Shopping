"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowLeft,
  Award,
  Box,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  ExternalLink,
  FileCheck2,
  FileText,
  History,
  Info,
  Plus,
  RefreshCw,
  Save,
  ShieldAlert,
  ShieldCheck,
  Truck,
  XCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiClient } from "@/lib/api/client";
import type {
  ClaimReviewHistoryItem,
  RetailerClaim,
  RetailerClaimCreateRequest,
  RetailerListingPassportDetail,
} from "@/types";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function RetailerListingPassportPage({ params }: PageProps) {
  const resolvedParams = use(params);
  const listingId = resolvedParams.id;

  const [passport, setPassport] = useState<RetailerListingPassportDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Listing passport form state
  const [condition, setCondition] = useState<string>("NEW");
  const [sellerWarranty, setSellerWarranty] = useState("");
  const [packagingNotes, setPackagingNotes] = useState("");
  const [fulfillmentNotes, setFulfillmentNotes] = useState("");

  // Claim submission form state
  const [showClaimForm, setShowClaimForm] = useState(false);
  const [claimScope, setClaimScope] = useState<"LISTING" | "PRODUCT">("LISTING");
  const [claimType, setClaimType] = useState("CERTIFICATION");
  const [claimKey, setClaimKey] = useState("");
  const [claimValue, setClaimValue] = useState("");
  const [evidenceUrl, setEvidenceUrl] = useState("");
  const [evidenceType, setEvidenceType] = useState("CERTIFICATE");
  const [evidenceNotes, setEvidenceNotes] = useState("");
  const [isPublicEvidence, setIsPublicEvidence] = useState(true);
  const [isSubmittingClaim, setIsSubmittingClaim] = useState(false);

  // Edit claim state
  const [editingClaim, setEditingClaim] = useState<RetailerClaim | null>(null);
  const [editClaimValue, setEditClaimValue] = useState("");
  const [editEvidenceUrl, setEditEvidenceUrl] = useState("");

  const [expandedHistoryClaimId, setExpandedHistoryClaimId] = useState<string | null>(null);
  const [claimHistoryMap, setClaimHistoryMap] = useState<Record<string, ClaimReviewHistoryItem[]>>({});
  const [loadingHistoryId, setLoadingHistoryId] = useState<string | null>(null);

  const toggleClaimHistory = async (claimId: string) => {
    if (expandedHistoryClaimId === claimId) {
      setExpandedHistoryClaimId(null);
      return;
    }
    setExpandedHistoryClaimId(claimId);
    if (!claimHistoryMap[claimId]) {
      setLoadingHistoryId(claimId);
      try {
        const hist = await apiClient.getRetailerClaimHistory(claimId);
        setClaimHistoryMap((prev) => ({ ...prev, [claimId]: hist }));
      } catch (err) {
        console.error("Failed to fetch claim history:", err);
      } finally {
        setLoadingHistoryId(null);
      }
    }
  };

  const loadPassport = useCallback(async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const data = await apiClient.getRetailerListingPassport(listingId);
      setPassport(data);
      setCondition(data.item_condition || "NEW");
      setSellerWarranty(data.seller_warranty || "");
      setPackagingNotes(data.packaging_notes || "");
      setFulfillmentNotes(data.fulfillment_notes || "");
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to load listing passport");
    } finally {
      setIsLoading(false);
    }
  }, [listingId]);

  useEffect(() => {
    loadPassport();
  }, [loadPassport]);

  const handleSaveListingDetails = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      const updated = await apiClient.upsertRetailerListingPassport(listingId, {
        item_condition: condition,
        seller_warranty: sellerWarranty || null,
        packaging_notes: packagingNotes || null,
        fulfillment_notes: fulfillmentNotes || null,
      });
      setPassport(updated);
      setSuccessMsg("Listing passport attributes saved successfully.");
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to save listing passport");
    } finally {
      setIsSaving(false);
    }
  };

  const handleCreateClaim = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!claimKey.trim() || !claimValue.trim()) {
      setErrorMsg("Please provide both claim key and claim value.");
      return;
    }
    setIsSubmittingClaim(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      const payload: RetailerClaimCreateRequest = {
        claim_scope: claimScope,
        claim_type: claimType,
        claim_key: claimKey.trim(),
        claim_value: claimValue.trim(),
        evidence_url: evidenceUrl.trim() || null,
        evidence_type: evidenceType,
        evidence_notes: evidenceNotes.trim() || null,
        is_public_evidence: isPublicEvidence,
      };
      await apiClient.submitRetailerClaim(listingId, payload);
      setSuccessMsg("Claim submitted for moderation! It will be reviewed by admin.");
      setShowClaimForm(false);
      setClaimKey("");
      setClaimValue("");
      setEvidenceUrl("");
      setEvidenceNotes("");
      await loadPassport();
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to submit claim");
    } finally {
      setIsSubmittingClaim(false);
    }
  };

  const handleUpdateClaim = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingClaim) return;
    setIsSubmittingClaim(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      await apiClient.updateRetailerClaim(editingClaim.id, {
        claim_value: editClaimValue.trim() || undefined,
        evidence_url: editEvidenceUrl.trim() || undefined,
      });
      setSuccessMsg("Claim updated. Review status reset to PENDING for moderation re-review.");
      setEditingClaim(null);
      await loadPassport();
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to update claim");
    } finally {
      setIsSubmittingClaim(false);
    }
  };

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8 max-w-4xl space-y-4 animate-pulse">
        <div className="h-6 w-32 bg-muted rounded" />
        <div className="h-10 w-64 bg-muted rounded" />
        <div className="h-64 bg-muted/40 rounded-xl" />
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl space-y-6">
      {/* Back Link */}
      <Link
        href="/retailer/listings"
        className="inline-flex items-center text-xs font-semibold text-muted-foreground hover:text-foreground transition-colors gap-1.5"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Back to Listings
      </Link>

      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-extrabold text-foreground tracking-tight">
              Listing Product Passport
            </h1>
            <Badge variant="outline" className="text-emerald-700 border-emerald-600/40 text-xs">
              Phase 2D
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Provide transparent, verifiable item condition, seller warranty terms, and compliance claims.
          </p>
        </div>

        <Button
          onClick={loadPassport}
          variant="outline"
          size="sm"
          className="text-xs gap-1.5 cursor-pointer"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </Button>
      </div>

      {/* Alerts */}
      {errorMsg && (
        <div className="p-4 rounded-xl border border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-400 text-xs flex items-center gap-2">
          <ShieldAlert className="h-4 w-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {successMsg && (
        <div className="p-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300 text-xs flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {/* Section 1: Listing Passport Details Form */}
      <Card className="rounded-2xl border shadow-xs">
        <div className="border-b bg-muted/20 px-6 py-4 flex items-center justify-between">
          <div>
            <h2 className="font-bold text-sm text-foreground flex items-center gap-2">
              <Box className="h-4 w-4 text-emerald-600" />
              Listing Specifications & Condition
            </h2>
            <p className="text-xs text-muted-foreground">
              These details apply specifically to your retailer listing and will be visible on product pages.
            </p>
          </div>
        </div>

        <CardContent className="p-6">
          <form onSubmit={handleSaveListingDetails} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold text-foreground mb-1">
                  Item Condition
                </label>
                <select
                  value={condition}
                  onChange={(e) => setCondition(e.target.value)}
                  className="w-full text-xs rounded-lg border bg-background px-3 py-2 text-foreground focus:ring-1 focus:ring-emerald-600 focus:outline-hidden"
                >
                  <option value="NEW">NEW — Brand new unopened</option>
                  <option value="REFURBISHED">REFURBISHED — Certified restored</option>
                  <option value="OPEN_BOX">OPEN_BOX — Like new packaging opened</option>
                  <option value="PRE_OWNED">PRE_OWNED — Tested pre-owned</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-foreground mb-1">
                  Seller Warranty
                </label>
                <Input
                  type="text"
                  placeholder="e.g. 6 Months Seller Replacement Warranty"
                  value={sellerWarranty}
                  onChange={(e) => setSellerWarranty(e.target.value)}
                  className="text-xs h-9"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold text-foreground mb-1">
                  Packaging Notes
                </label>
                <Input
                  type="text"
                  placeholder="e.g. Ships in certified tamper-evident eco pouch"
                  value={packagingNotes}
                  onChange={(e) => setPackagingNotes(e.target.value)}
                  className="text-xs h-9"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-foreground mb-1">
                  Fulfillment & Dispatch Notes
                </label>
                <Input
                  type="text"
                  placeholder="e.g. Dispatched same day from Mumbai facility"
                  value={fulfillmentNotes}
                  onChange={(e) => setFulfillmentNotes(e.target.value)}
                  className="text-xs h-9"
                />
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <Button
                type="submit"
                disabled={isSaving}
                className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs h-9 px-4 gap-1.5 cursor-pointer"
              >
                <Save className="h-3.5 w-3.5" />
                {isSaving ? "Saving..." : "Save Listing Attributes"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Section 2: Submitted Claims & Moderation Status */}
      <Card className="rounded-2xl border shadow-xs">
        <div className="border-b bg-muted/20 px-6 py-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-bold text-sm text-foreground flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-emerald-600" />
              Verified Claims & Supporting Evidence
            </h2>
            <p className="text-xs text-muted-foreground">
              Submit proof for regulatory certifications, origin claims, or lab reports.
            </p>
          </div>

          <Button
            onClick={() => setShowClaimForm(!showClaimForm)}
            size="sm"
            className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs gap-1 cursor-pointer"
          >
            <Plus className="h-3.5 w-3.5" />
            {showClaimForm ? "Close Form" : "Submit New Claim"}
          </Button>
        </div>

        <CardContent className="p-6 space-y-6">
          {/* Create Claim Form */}
          {showClaimForm && (
            <form
              onSubmit={handleCreateClaim}
              className="p-4 rounded-xl border border-emerald-600/30 bg-emerald-600/5 space-y-4"
            >
              <h3 className="font-bold text-xs uppercase tracking-wider text-emerald-950 dark:text-emerald-200">
                New Compliance Claim Submission
              </h3>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-foreground mb-1">
                    Claim Scope
                  </label>
                  <select
                    value={claimScope}
                    onChange={(e) => setClaimScope(e.target.value as "LISTING" | "PRODUCT")}
                    className="w-full text-xs rounded-lg border bg-background px-3 py-2 text-foreground"
                  >
                    <option value="LISTING">Listing Specific</option>
                    <option value="PRODUCT">Canonical Product</option>
                  </select>
                </div>

                <div>
                  <label className="block text-[11px] font-bold text-foreground mb-1">
                    Claim Type
                  </label>
                  <select
                    value={claimType}
                    onChange={(e) => setClaimType(e.target.value)}
                    className="w-full text-xs rounded-lg border bg-background px-3 py-2 text-foreground"
                  >
                    <option value="CERTIFICATION">Certification / License</option>
                    <option value="ORIGIN">Country / State of Origin</option>
                    <option value="SPECIFICATION">Technical Specification</option>
                    <option value="WARRANTY">Warranty Declaration</option>
                    <option value="MATERIAL">Material Composition</option>
                  </select>
                </div>

                <div>
                  <label className="block text-[11px] font-bold text-foreground mb-1">
                    Claim Key (Identifier)
                  </label>
                  <Input
                    type="text"
                    placeholder="e.g. fssai_license"
                    value={claimKey}
                    onChange={(e) => setClaimKey(e.target.value)}
                    required
                    className="text-xs h-9"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-bold text-foreground mb-1">
                  Claim Value (The factual statement or license number)
                </label>
                <Input
                  type="text"
                  placeholder="e.g. FSSAI License # 10019043000000"
                  value={claimValue}
                  onChange={(e) => setClaimValue(e.target.value)}
                  required
                  className="text-xs h-9"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-foreground mb-1">
                    Evidence URL (Direct link to cert/report)
                  </label>
                  <Input
                    type="url"
                    placeholder="https://example.gov.in/cert.pdf"
                    value={evidenceUrl}
                    onChange={(e) => setEvidenceUrl(e.target.value)}
                    className="text-xs h-9"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-bold text-foreground mb-1">
                    Evidence Document Type
                  </label>
                  <select
                    value={evidenceType}
                    onChange={(e) => setEvidenceType(e.target.value)}
                    className="w-full text-xs rounded-lg border bg-background px-3 py-2 text-foreground"
                  >
                    <option value="CERTIFICATE">Government / Agency Certificate</option>
                    <option value="LAB_REPORT">Authorized Lab Test Report</option>
                    <option value="DOCUMENT">Manufacturer Invoice / Bill</option>
                    <option value="MANUFACTURER_URL">Manufacturer Web Reference</option>
                  </select>
                </div>
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="public_toggle"
                  checked={isPublicEvidence}
                  onChange={(e) => setIsPublicEvidence(e.target.checked)}
                  className="h-4 w-4 rounded text-emerald-600 focus:ring-emerald-500"
                />
                <label htmlFor="public_toggle" className="text-xs text-foreground cursor-pointer">
                  Allow customers to view evidence document once verified by Admin
                </label>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setShowClaimForm(false)}
                  className="text-xs"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={isSubmittingClaim}
                  size="sm"
                  className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs cursor-pointer"
                >
                  {isSubmittingClaim ? "Submitting..." : "Submit for Moderation"}
                </Button>
              </div>
            </form>
          )}

          {/* Edit Claim Modal / Inline Form */}
          {editingClaim && (
            <form
              onSubmit={handleUpdateClaim}
              className="p-4 rounded-xl border border-amber-600/30 bg-amber-600/5 space-y-3"
            >
              <div className="flex items-center justify-between">
                <h4 className="font-bold text-xs text-amber-950 dark:text-amber-200">
                  Editing Claim: {editingClaim.claim_key}
                </h4>
                <Badge variant="outline" className="text-[10px] text-amber-700 border-amber-600/40">
                  Will Re-Trigger PENDING Review
                </Badge>
              </div>

              <div>
                <label className="block text-[11px] font-bold text-foreground mb-1">
                  Updated Claim Value
                </label>
                <Input
                  type="text"
                  value={editClaimValue}
                  onChange={(e) => setEditClaimValue(e.target.value)}
                  required
                  className="text-xs h-9"
                />
              </div>

              <div>
                <label className="block text-[11px] font-bold text-foreground mb-1">
                  Updated Evidence URL
                </label>
                <Input
                  type="url"
                  value={editEvidenceUrl}
                  onChange={(e) => setEditEvidenceUrl(e.target.value)}
                  className="text-xs h-9"
                />
              </div>

              <div className="flex justify-end gap-2 pt-1">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setEditingClaim(null)}
                  className="text-xs"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={isSubmittingClaim}
                  size="sm"
                  className="bg-amber-600 hover:bg-amber-700 text-black font-bold text-xs cursor-pointer"
                >
                  {isSubmittingClaim ? "Saving..." : "Save & Request Re-Review"}
                </Button>
              </div>
            </form>
          )}

          {/* Claims List */}
          {(!passport?.claims || passport.claims.length === 0) ? (
            <div className="text-center py-6 text-xs text-muted-foreground border border-dashed rounded-xl p-4">
              <FileText className="h-6 w-6 mx-auto mb-1 text-muted-foreground/60" />
              <span>No claims submitted for this listing yet. Use the button above to add one.</span>
            </div>
          ) : (
            <div className="space-y-3">
              {passport.claims.map((claim) => (
                <div
                  key={claim.id}
                  className="p-4 rounded-xl border bg-card/60 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-foreground">
                        {claim.claim_key}
                      </span>
                      <span className="text-muted-foreground">•</span>
                      <span className="text-muted-foreground uppercase text-[10px]">
                        {claim.claim_type}
                      </span>
                      <Badge variant="outline" className="text-[10px] py-0 px-1.5 h-4">
                        {claim.claim_scope}
                      </Badge>
                    </div>
                    <p className="text-muted-foreground">{claim.claim_value}</p>

                    {claim.evidence_url && (
                      <a
                        href={claim.evidence_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-[11px] text-emerald-700 dark:text-emerald-400 hover:underline pt-0.5"
                      >
                        Evidence Reference <ExternalLink className="h-3 w-3" />
                      </a>
                    )}

                    {/* Moderation Feedback notice (preserved even after re-review trigger) */}
                    {claim.rejection_reason && (
                      <div className="mt-2 p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-900 dark:text-amber-200 text-[11px] space-y-1">
                        <div className="flex items-center gap-1.5 font-bold text-amber-800 dark:text-amber-300">
                          <AlertTriangle className="h-3.5 w-3.5" />
                          <span>
                            {claim.review_status === "PENDING"
                              ? "Previous Moderation Feedback (Under Re-Review):"
                              : "Moderation Feedback:"}
                          </span>
                        </div>
                        <p className="pl-5">{claim.rejection_reason}</p>
                      </div>
                    )}

                    {/* Expandable Claim Review History */}
                    {expandedHistoryClaimId === claim.id && (
                      <div className="mt-3 p-3 rounded-xl border border-muted bg-muted/20 space-y-2 text-[11px]">
                        <div className="flex items-center justify-between font-bold text-foreground">
                          <span className="flex items-center gap-1.5">
                            <History className="h-3.5 w-3.5 text-emerald-600" />
                            Claim Review & Revision History
                          </span>
                          <span className="text-[10px] text-muted-foreground font-normal">
                            Version {claim.version || 1}
                          </span>
                        </div>

                        {loadingHistoryId === claim.id ? (
                          <div className="py-2 text-center text-muted-foreground flex items-center justify-center gap-1.5">
                            <RefreshCw className="h-3 w-3 animate-spin" />
                            Loading audit trail...
                          </div>
                        ) : (claimHistoryMap[claim.id] || claim.review_history || []).length === 0 ? (
                          <div className="py-1 text-muted-foreground">No revision history found.</div>
                        ) : (
                          <div className="space-y-1.5 border-l-2 border-emerald-600/30 pl-3 ml-1 mt-2">
                            {(claimHistoryMap[claim.id] || claim.review_history || []).map((h) => (
                              <div key={h.id} className="relative pb-1">
                                <div className="flex items-center gap-2">
                                  <Badge
                                    variant="outline"
                                    className={`text-[9px] py-0 px-1 font-bold ${
                                      h.action === "VERIFIED"
                                        ? "text-emerald-700 border-emerald-600/40 bg-emerald-50 dark:bg-emerald-950/40"
                                        : h.action === "REJECTED"
                                        ? "text-red-700 border-red-600/40 bg-red-50 dark:bg-red-950/40"
                                        : h.action === "REVISED"
                                        ? "text-amber-700 border-amber-600/40 bg-amber-50 dark:bg-amber-950/40"
                                        : "text-blue-700 border-blue-600/40 bg-blue-50 dark:bg-blue-950/40"
                                    }`}
                                  >
                                    {h.action}
                                  </Badge>
                                  <span className="text-muted-foreground text-[10px]">
                                    {new Date(h.created_at).toLocaleString()}
                                  </span>
                                </div>
                                <p className="text-foreground mt-0.5">&ldquo;{h.claim_value}&rdquo;</p>
                                {h.rejection_reason && (
                                  <p className="text-red-600 dark:text-red-400 font-medium">
                                    Reason: {h.rejection_reason}
                                  </p>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
                    {claim.review_status === "VERIFIED" ? (
                      <Badge className="bg-emerald-600 text-white flex items-center gap-1 text-[11px]">
                        <CheckCircle2 className="h-3 w-3" />
                        Verified
                      </Badge>
                    ) : claim.review_status === "PENDING" ? (
                      <Badge variant="outline" className="text-amber-700 dark:text-amber-300 border-amber-600/40 bg-amber-50 dark:bg-amber-950/40 flex items-center gap-1 text-[11px]">
                        <Clock className="h-3 w-3" />
                        Awaiting Review
                      </Badge>
                    ) : (
                      <Badge variant="destructive" className="flex items-center gap-1 text-[11px]">
                        <XCircle className="h-3 w-3" />
                        Rejected
                      </Badge>
                    )}

                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => toggleClaimHistory(claim.id)}
                      className="text-xs h-8 px-2 text-muted-foreground hover:text-foreground gap-1"
                    >
                      <History className="h-3.5 w-3.5" />
                      {expandedHistoryClaimId === claim.id ? (
                        <ChevronUp className="h-3 w-3" />
                      ) : (
                        <ChevronDown className="h-3 w-3" />
                      )}
                    </Button>

                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setEditingClaim(claim);
                        setEditClaimValue(claim.claim_value);
                        setEditEvidenceUrl(claim.evidence_url || "");
                      }}
                      className="text-xs h-8 px-2 text-muted-foreground hover:text-foreground"
                    >
                      Edit
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
