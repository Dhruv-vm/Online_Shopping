"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  ExternalLink,
  FileCheck2,
  Filter,
  History,
  Info,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  Store,
  XCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiClient } from "@/lib/api/client";
import type { AdminClaim, AdminClaimQueueResponse, ClaimReviewHistoryItem } from "@/types";

export default function AdminPassportModerationPage() {
  const [claims, setClaims] = useState<AdminClaim[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [statusFilter, setStatusFilter] = useState("PENDING");
  const [scopeFilter, setScopeFilter] = useState("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  // Claim review history inspection state
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
        const hist = await apiClient.getAdminClaimHistory(claimId);
        setClaimHistoryMap((prev) => ({ ...prev, [claimId]: hist }));
      } catch (err) {
        console.error("Failed to fetch admin claim history:", err);
      } finally {
        setLoadingHistoryId(null);
      }
    }
  };
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Reject modal state
  const [rejectingClaim, setRejectingClaim] = useState<AdminClaim | null>(null);
  const [rejectionReason, setRejectionReason] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);

  const loadQueue = useCallback(async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const res: AdminClaimQueueResponse = await apiClient.getAdminClaimsQueue({
        status: statusFilter,
        scope: scopeFilter,
        search: searchQuery.trim() || undefined,
        page,
        limit: 15,
      });
      setClaims(res.items);
      setTotal(res.total);
      setPages(res.pages);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to load moderation queue");
    } finally {
      setIsLoading(false);
    }
  }, [page, statusFilter, scopeFilter, searchQuery]);

  useEffect(() => {
    loadQueue();
  }, [loadQueue]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    loadQueue();
  };

  const handleVerify = async (claimId: string) => {
    setIsProcessing(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      await apiClient.verifyAdminClaim(claimId);
      setSuccessMsg("Claim successfully verified and published.");
      await loadQueue();
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to verify claim");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleRejectSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!rejectingClaim || !rejectionReason.trim()) return;
    setIsProcessing(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      await apiClient.rejectAdminClaim(rejectingClaim.id, rejectionReason.trim());
      setSuccessMsg("Claim rejected and feedback provided to the retailer.");
      setRejectingClaim(null);
      setRejectionReason("");
      await loadQueue();
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to reject claim");
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="container mx-auto px-4 py-8 max-w-5xl space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-extrabold text-foreground tracking-tight flex items-center gap-2">
              <FileCheck2 className="h-6 w-6 text-emerald-600" />
              Product Passport Moderation Queue
            </h1>
            <Badge variant="outline" className="text-emerald-700 border-emerald-600/40 text-xs">
              Phase 2D Admin
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Audit compliance certifications, origin claims, and evidence references before publishing to customers.
          </p>
        </div>

        <Button
          onClick={loadQueue}
          variant="outline"
          size="sm"
          className="text-xs gap-1.5 cursor-pointer"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh Queue
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

      {/* Filter and Search Bar */}
      <Card className="rounded-2xl border shadow-xs">
        <CardContent className="p-4">
          <form onSubmit={handleSearch} className="flex flex-wrap items-center gap-3">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="h-3.5 w-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <Input
                type="text"
                placeholder="Search key, value, retailer or product..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="text-xs pl-8 h-9"
              />
            </div>

            <div className="flex items-center gap-2">
              <select
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  setPage(1);
                }}
                className="text-xs rounded-lg border bg-background px-3 py-2 text-foreground h-9"
              >
                <option value="PENDING">Status: Awaiting Review (PENDING)</option>
                <option value="VERIFIED">Status: Verified</option>
                <option value="REJECTED">Status: Rejected</option>
                <option value="ALL">Status: All Statuses</option>
              </select>

              <select
                value={scopeFilter}
                onChange={(e) => {
                  setScopeFilter(e.target.value);
                  setPage(1);
                }}
                className="text-xs rounded-lg border bg-background px-3 py-2 text-foreground h-9"
              >
                <option value="ALL">Scope: All Scopes</option>
                <option value="LISTING">Scope: Listing Only</option>
                <option value="PRODUCT">Scope: Product Only</option>
              </select>

              <Button type="submit" size="sm" className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs h-9 px-4 cursor-pointer">
                Search
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Claims Queue Table / List */}
      <Card className="rounded-2xl border shadow-xs overflow-hidden">
        <div className="border-b bg-muted/20 px-6 py-3.5 flex items-center justify-between text-xs text-muted-foreground">
          <span className="font-semibold text-foreground">
            Total Claims in Queue: {total}
          </span>
          <span>
            Page {page} of {pages}
          </span>
        </div>

        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-8 text-center text-xs text-muted-foreground animate-pulse space-y-2">
              <RefreshCw className="h-6 w-6 mx-auto animate-spin text-emerald-600" />
              <span>Loading moderation queue...</span>
            </div>
          ) : claims.length === 0 ? (
            <div className="p-12 text-center text-xs text-muted-foreground space-y-2">
              <CheckCircle2 className="h-8 w-8 mx-auto text-emerald-600/70" />
              <p className="text-sm font-bold text-foreground">No Claims Awaiting Review</p>
              <p>The queue is clear for the selected filters.</p>
            </div>
          ) : (
            <div className="divide-y">
              {claims.map((claim) => (
                <div
                  key={claim.id}
                  className="p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:bg-muted/10 transition-colors text-xs"
                >
                  <div className="space-y-1.5 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-bold text-sm text-foreground">
                        {claim.claim_key}
                      </span>
                      <span className="text-muted-foreground">•</span>
                      <Badge variant="secondary" className="text-[10px] uppercase font-bold">
                        {claim.claim_type}
                      </Badge>
                      <Badge variant="outline" className="text-[10px]">
                        {claim.claim_scope}
                      </Badge>

                      {claim.review_status === "VERIFIED" ? (
                        <Badge className="bg-emerald-600 text-white text-[10px] flex items-center gap-1">
                          <CheckCircle2 className="h-2.5 w-2.5" />
                          Verified
                        </Badge>
                      ) : claim.review_status === "PENDING" ? (
                        <Badge variant="outline" className="text-amber-700 dark:text-amber-300 border-amber-600/40 bg-amber-50 dark:bg-amber-950/40 text-[10px] flex items-center gap-1">
                          <Clock className="h-2.5 w-2.5" />
                          Pending Review
                        </Badge>
                      ) : (
                        <Badge variant="destructive" className="text-[10px] flex items-center gap-1">
                          <XCircle className="h-2.5 w-2.5" />
                          Rejected
                        </Badge>
                      )}
                    </div>

                    <p className="text-sm font-semibold text-foreground">
                      &ldquo;{claim.claim_value}&rdquo;
                    </p>

                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-muted-foreground text-[11px] pt-0.5">
                      {claim.retailer_name && (
                        <span className="flex items-center gap-1 font-medium text-foreground">
                          <Store className="h-3 w-3 text-emerald-600" />
                          {claim.retailer_name}
                        </span>
                      )}
                      {claim.product_name && (
                        <span>Product: {claim.product_name}</span>
                      )}
                      <span>Doc Type: {claim.evidence_type}</span>
                      <span>Public: {claim.is_public_evidence ? "Yes" : "Private only"}</span>
                    </div>

                    {claim.evidence_url && (
                      <div className="pt-1">
                        <a
                          href={claim.evidence_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-700 dark:text-emerald-400 hover:underline"
                        >
                          Inspect Evidence Document <ExternalLink className="h-3 w-3" />
                        </a>
                        {claim.evidence_notes && (
                          <p className="text-[11px] text-muted-foreground mt-0.5">
                            Note: {claim.evidence_notes}
                          </p>
                        )}
                      </div>
                    )}

                    {claim.rejection_reason && (
                      <div className="p-2 rounded bg-red-500/10 text-red-700 dark:text-red-400 text-[11px] border border-red-500/20">
                        <span className="font-bold">Prior Moderation Feedback: </span>
                        {claim.rejection_reason}
                      </div>
                    )}

                    {/* Expandable History Timeline for Admin */}
                    {expandedHistoryClaimId === claim.id && (
                      <div className="mt-3 p-3 rounded-xl border border-muted bg-muted/20 space-y-2 text-[11px]">
                        <div className="flex items-center justify-between font-bold text-foreground">
                          <span className="flex items-center gap-1.5">
                            <History className="h-3.5 w-3.5 text-emerald-600" />
                            Complete Moderation & Revision Audit Trail
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
                          <div className="space-y-2 border-l-2 border-emerald-600/30 pl-3 ml-1 mt-2">
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
                                  {h.reviewer_id && (
                                    <span className="text-[10px] text-muted-foreground">
                                      Reviewer: {h.reviewer_id.slice(0, 8)}...
                                    </span>
                                  )}
                                </div>
                                <p className="text-foreground mt-0.5">&ldquo;{h.claim_value}&rdquo;</p>
                                {h.evidence_url && (
                                  <a
                                    href={h.evidence_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-[10px] text-emerald-700 dark:text-emerald-400 hover:underline inline-flex items-center gap-1"
                                  >
                                    Doc URL <ExternalLink className="h-2.5 w-2.5" />
                                  </a>
                                )}
                                {h.rejection_reason && (
                                  <p className="text-red-600 dark:text-red-400 font-medium">
                                    Rejection: {h.rejection_reason}
                                  </p>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2 shrink-0 self-end md:self-center">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => toggleClaimHistory(claim.id)}
                      className="text-xs h-8 px-2 text-muted-foreground hover:text-foreground gap-1"
                    >
                      <History className="h-3.5 w-3.5" />
                      History
                      {expandedHistoryClaimId === claim.id ? (
                        <ChevronUp className="h-3 w-3" />
                      ) : (
                        <ChevronDown className="h-3 w-3" />
                      )}
                    </Button>

                    {claim.review_status !== "VERIFIED" && (
                      <Button
                        size="sm"
                        disabled={isProcessing}
                        onClick={() => handleVerify(claim.id)}
                        className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs h-8 cursor-pointer"
                      >
                        Verify & Publish
                      </Button>
                    )}

                    {claim.review_status !== "REJECTED" && (
                      <Button
                        size="sm"
                        variant="destructive"
                        disabled={isProcessing}
                        onClick={() => {
                          setRejectingClaim(claim);
                          setRejectionReason("");
                        }}
                        className="text-xs h-8 cursor-pointer"
                      >
                        Reject...
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>

        {/* Pagination */}
        {pages > 1 && (
          <div className="border-t bg-muted/20 px-6 py-3 flex items-center justify-between text-xs">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="text-xs"
            >
              Previous
            </Button>
            <span>
              Page {page} of {pages}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= pages}
              onClick={() => setPage((p) => Math.min(pages, p + 1))}
              className="text-xs"
            >
              Next
            </Button>
          </div>
        )}
      </Card>

      {/* Reject Modal */}
      {rejectingClaim && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
          <Card className="w-full max-w-md rounded-2xl shadow-xl border bg-card">
            <div className="border-b px-6 py-4">
              <h3 className="font-bold text-sm text-foreground">
                Reject Claim: {rejectingClaim.claim_key}
              </h3>
              <p className="text-xs text-muted-foreground mt-0.5">
                Provide a clear reason so the retailer understands what evidence is missing or mismatched.
              </p>
            </div>

            <CardContent className="p-6">
              <form onSubmit={handleRejectSubmit} className="space-y-4">
                <div>
                  <label className="block text-xs font-bold text-foreground mb-1">
                    Mandatory Rejection Reason
                  </label>
                  <textarea
                    rows={4}
                    required
                    value={rejectionReason}
                    onChange={(e) => setRejectionReason(e.target.value)}
                    placeholder="e.g. Government registration number mismatch on official portal..."
                    className="w-full text-xs rounded-lg border bg-background p-3 text-foreground focus:ring-1 focus:ring-emerald-600 focus:outline-hidden"
                  />
                </div>

                <div className="flex justify-end gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setRejectingClaim(null)}
                    className="text-xs"
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    variant="destructive"
                    size="sm"
                    disabled={isProcessing || !rejectionReason.trim()}
                    className="text-xs font-bold cursor-pointer"
                  >
                    {isProcessing ? "Rejecting..." : "Confirm Rejection"}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
