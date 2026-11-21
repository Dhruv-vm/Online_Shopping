"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Store,
  ShieldCheck,
  ShieldAlert,
  Search,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  FileText,
  Clock,
  Eye,
  X,
  Check,
  Ban,
  ExternalLink,
  BarChart3,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiClient } from "@/lib/api/client";
import type {
  AdminRetailerListItem,
  AdminRetailerDetailResponse,
} from "@/types";

export default function AdminRetailersPage() {
  const [retailers, setRetailers] = useState<AdminRetailerListItem[]>([]);
  const [filterStatus, setFilterStatus] = useState<string>("ALL");
  const [filterState, setFilterState] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Detail Modal / Inspection
  const [selectedRetailerId, setSelectedRetailerId] = useState<string | null>(null);
  const [retailerDetail, setRetailerDetail] = useState<AdminRetailerDetailResponse | null>(null);
  const [isDetailLoading, setIsDetailLoading] = useState(false);

  // Status Action Modal
  const [actionModal, setActionModal] = useState<{
    isOpen: boolean;
    retailerId: string;
    retailerName: string;
    targetStatus: "VERIFIED" | "REJECTED" | "SUSPENDED";
    reason: string;
  } | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  // Document Verification Action
  const [docActionLoading, setDocActionLoading] = useState<string | null>(null);

  const loadRetailers = async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const data = await apiClient.listAdminRetailers();
      setRetailers(data);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to load retailers.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadRetailers();
  }, []);

  const openInspection = async (retailerId: string) => {
    setSelectedRetailerId(retailerId);
    setIsDetailLoading(true);
    setErrorMsg(null);
    try {
      const detail = await apiClient.getAdminRetailer(retailerId);
      setRetailerDetail(detail);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to load retailer details.");
    } finally {
      setIsDetailLoading(false);
    }
  };

  const closeInspection = () => {
    setSelectedRetailerId(null);
    setRetailerDetail(null);
  };

  const handleStatusSubmit = async () => {
    if (!actionModal) return;
    setActionLoading(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      const updated = await apiClient.verifyRetailer(
        actionModal.retailerId,
        actionModal.targetStatus,
        actionModal.reason.trim() || undefined
      );
      setRetailers((prev) =>
        prev.map((r) => (r.id === actionModal.retailerId ? updated : r))
      );
      setSuccessMsg(
        `Retailer "${actionModal.retailerName}" status updated to ${actionModal.targetStatus}.`
      );
      setActionModal(null);
      // Refresh modal if open
      if (selectedRetailerId === actionModal.retailerId) {
        const detail = await apiClient.getAdminRetailer(actionModal.retailerId);
        setRetailerDetail(detail);
      }
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to update retailer status.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleDocVerify = async (
    docId: string,
    status: "APPROVED" | "REJECTED"
  ) => {
    if (!selectedRetailerId) return;
    setDocActionLoading(docId);
    setErrorMsg(null);
    try {
      await apiClient.verifyAdminRetailerDocument(selectedRetailerId, docId, status);
      const detail = await apiClient.getAdminRetailer(selectedRetailerId);
      setRetailerDetail(detail);
      setSuccessMsg(`Document marked as ${status}.`);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to update document status.");
    } finally {
      setDocActionLoading(null);
    }
  };

  const uniqueStates = Array.from(
    new Set(retailers.map((r) => r.state).filter((s): s is string => Boolean(s)))
  ).sort();

  const filteredRetailers = retailers.filter((r) => {
    const matchesStatus =
      filterStatus === "ALL" || r.verification_status === filterStatus;
    const matchesState =
      filterState === "ALL" || (r.state && r.state.toUpperCase() === filterState);
    const matchesSearch =
      !searchQuery ||
      r.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (r.owner_email && r.owner_email.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (r.owner_name && r.owner_name.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (r.state && r.state.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchesStatus && matchesState && matchesSearch;
  });

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "VERIFIED":
        return <Badge className="bg-emerald-600 text-white font-medium">Verified</Badge>;
      case "PENDING":
        return <Badge className="bg-amber-500 text-white font-medium">Pending Review</Badge>;
      case "SUSPENDED":
        return <Badge variant="destructive" className="font-medium">Suspended</Badge>;
      case "REJECTED":
        return <Badge className="bg-zinc-600 text-white font-medium">Rejected</Badge>;
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
            <ShieldCheck className="h-6 w-6 text-purple-600" />
            Retailer Verification & Compliance
          </h1>
          <p className="text-sm text-muted-foreground">
            Audit merchant applications, verify compliance documents, and govern marketplace seller privileges.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={loadRetailers}
          disabled={isLoading}
          className="gap-2 shrink-0"
        >
          <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {/* Notifications */}
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

      {/* Filters & Search */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-card p-3 rounded-xl border">
        <div className="flex flex-wrap gap-1.5 w-full sm:w-auto">
          {["ALL", "PENDING", "VERIFIED", "SUSPENDED", "REJECTED"].map((tab) => (
            <button
              key={tab}
              onClick={() => setFilterStatus(tab)}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
                filterStatus === tab
                  ? "bg-purple-600 text-white"
                  : "bg-muted/60 text-muted-foreground hover:bg-muted hover:text-foreground"
              }`}
            >
              {tab === "ALL" ? "All Retailers" : tab.charAt(0) + tab.slice(1).toLowerCase()}
              <span className="ml-1.5 opacity-80">
                ({tab === "ALL"
                  ? retailers.length
                  : retailers.filter((r) => r.verification_status === tab).length})
              </span>
            </button>
          ))}
        </div>
        <div className="flex flex-col sm:flex-row items-center gap-2 w-full sm:w-auto">
          {uniqueStates.length > 0 && (
            <select
              value={filterState}
              onChange={(e) => setFilterState(e.target.value)}
              className="h-9 text-xs px-2.5 rounded-md border border-input bg-background text-foreground shadow-xs w-full sm:w-36"
              aria-label="Filter by registered state"
            >
              <option value="ALL">All States ({uniqueStates.length})</option>
              {uniqueStates.map((st) => (
                <option key={st} value={st.toUpperCase()}>
                  {st}
                </option>
              ))}
            </select>
          )}
          <div className="relative w-full sm:w-72">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search name, email, state..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 h-9 text-xs"
            />
          </div>
        </div>
      </div>

      {/* Retailers Table */}
      <div className="rounded-xl border bg-card shadow-xs overflow-hidden">
        {isLoading ? (
          <div className="py-16 text-center text-sm text-muted-foreground">
            <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-solid border-purple-600 border-r-transparent mb-2" />
            <p>Loading retailer roster...</p>
          </div>
        ) : filteredRetailers.length === 0 ? (
          <div className="py-16 text-center text-sm text-muted-foreground">
            <Store className="h-8 w-8 mx-auto mb-2 text-muted-foreground/60" />
            <p className="font-medium text-foreground">No retailers found</p>
            <p className="text-xs text-muted-foreground mt-1">
              {searchQuery || filterStatus !== "ALL"
                ? "Try adjusting your search criteria or status filter."
                : "No merchant accounts have registered yet."}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-muted/50 border-b text-muted-foreground font-semibold">
                <tr>
                  <th className="px-4 py-3">Store Name & Slug</th>
                  <th className="px-4 py-3">Owner Contact</th>
                  <th className="px-4 py-3">Registered State</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Created</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filteredRetailers.map((r) => (
                  <tr key={r.id} className="hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-3">
                      <div className="font-semibold text-foreground text-sm">{r.name}</div>
                      <div className="text-[11px] text-muted-foreground font-mono">
                        slug: {r.slug}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="text-foreground">{r.owner_email || r.contact_email || "—"}</div>
                      <div className="text-muted-foreground text-[11px]">{r.contact_phone || "—"}</div>
                    </td>
                    <td className="px-4 py-3 text-foreground font-medium">
                      {r.state || "—"}
                    </td>
                    <td className="px-4 py-3">
                      {getStatusBadge(r.verification_status)}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {new Date(r.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <Link href={`/admin/retailers/${r.id}`}>
                          <Button
                            variant="outline"
                            size="sm"
                            className="h-7 text-xs px-2.5 gap-1 text-purple-700 hover:text-purple-800 border-purple-200 dark:border-purple-800/40 hover:bg-purple-50 dark:hover:bg-purple-950/40"
                          >
                            <BarChart3 className="h-3.5 w-3.5" />
                            Analytics
                          </Button>
                        </Link>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => openInspection(r.id)}
                          className="h-7 text-xs px-2.5 gap-1"
                        >
                          <Eye className="h-3.5 w-3.5" />
                          Inspect
                        </Button>
                        {r.verification_status === "PENDING" && (
                          <>
                            <Button
                              size="sm"
                              onClick={() =>
                                setActionModal({
                                  isOpen: true,
                                  retailerId: r.id,
                                  retailerName: r.name,
                                  targetStatus: "VERIFIED",
                                  reason: "",
                                })
                              }
                              className="h-7 text-xs px-2.5 bg-brand-yellow hover:bg-brand-yellow-dark text-ink"
                            >
                              Approve
                            </Button>
                            <Button
                              variant="destructive"
                              size="sm"
                              onClick={() =>
                                setActionModal({
                                  isOpen: true,
                                  retailerId: r.id,
                                  retailerName: r.name,
                                  targetStatus: "REJECTED",
                                  reason: "",
                                })
                              }
                              className="h-7 text-xs px-2.5"
                            >
                              Reject
                            </Button>
                          </>
                        )}
                        {r.verification_status === "VERIFIED" && (
                          <Button
                            variant="destructive"
                            size="sm"
                            onClick={() =>
                              setActionModal({
                                isOpen: true,
                                retailerId: r.id,
                                retailerName: r.name,
                                targetStatus: "SUSPENDED",
                                reason: "",
                              })
                            }
                            className="h-7 text-xs px-2.5"
                          >
                            Suspend
                          </Button>
                        )}
                        {(r.verification_status === "SUSPENDED" ||
                          r.verification_status === "REJECTED") && (
                          <Button
                            size="sm"
                            onClick={() =>
                              setActionModal({
                                isOpen: true,
                                retailerId: r.id,
                                retailerName: r.name,
                                targetStatus: "VERIFIED",
                                reason: "",
                              })
                            }
                            className="h-7 text-xs px-2.5 bg-purple-600 hover:bg-purple-700 text-white"
                          >
                            Reactivate
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Retailer Detail Inspection Drawer / Modal */}
      {selectedRetailerId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
          <div className="bg-card border rounded-2xl w-full max-w-3xl max-h-[90vh] overflow-y-auto shadow-2xl p-6 space-y-6">
            <div className="flex items-center justify-between border-b pb-4">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-xl font-bold tracking-tight text-foreground">
                    {retailerDetail ? retailerDetail.name : "Loading Merchant..."}
                  </h2>
                  {retailerDetail && getStatusBadge(retailerDetail.verification_status)}
                </div>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Retailer ID: <code className="font-mono">{selectedRetailerId}</code>
                </p>
              </div>
              <Button variant="ghost" size="sm" onClick={closeInspection} className="h-8 w-8 p-0">
                <X className="h-4 w-4" />
              </Button>
            </div>

            {isDetailLoading || !retailerDetail ? (
              <div className="py-12 text-center text-sm text-muted-foreground">
                <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-solid border-purple-600 border-r-transparent mb-2" />
                <p>Fetching merchant compliance dossier...</p>
              </div>
            ) : (
              <div className="space-y-6">
                {/* Details Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 bg-muted/30 p-4 rounded-xl text-xs">
                  <div>
                    <span className="text-muted-foreground">Owner Name:</span>
                    <p className="font-semibold text-foreground">{retailerDetail.owner_name || "—"}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Owner Email:</span>
                    <p className="font-semibold text-foreground">{retailerDetail.owner_email || "—"}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Contact Phone:</span>
                    <p className="font-semibold text-foreground">{retailerDetail.contact_phone || "—"}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Registered State:</span>
                    <p className="font-semibold text-foreground">{retailerDetail.state || "—"}</p>
                  </div>
                  <div className="sm:col-span-2">
                    <span className="text-muted-foreground">Business Address:</span>
                    <p className="font-semibold text-foreground">{retailerDetail.business_address || "—"}</p>
                  </div>
                </div>

                {retailerDetail.rejection_reason && (
                  <div className="p-3 bg-red-50 dark:bg-red-950/40 border border-red-500/30 rounded-lg text-xs text-red-700 dark:text-red-300">
                    <strong>Previous Decision Reason:</strong> {retailerDetail.rejection_reason}
                  </div>
                )}

                {/* Submitted Compliance Documents */}
                <div className="space-y-3">
                  <h3 className="text-sm font-bold tracking-tight text-foreground flex items-center gap-2">
                    <FileText className="h-4 w-4 text-purple-600" />
                    Submitted Verification Documents ({retailerDetail.documents.length})
                  </h3>
                  {retailerDetail.documents.length === 0 ? (
                    <p className="text-xs text-muted-foreground italic bg-muted/20 p-4 rounded-lg">
                      No compliance documents submitted yet by this merchant.
                    </p>
                  ) : (
                    <div className="space-y-2">
                      {retailerDetail.documents.map((doc) => (
                        <div
                          key={doc.id}
                          className="flex items-center justify-between p-3 rounded-xl border bg-card text-xs gap-3"
                        >
                          <div>
                            <div className="font-semibold text-foreground flex items-center gap-2">
                              {doc.document_type}
                              <Badge
                                variant={
                                  doc.status === "APPROVED" || doc.status === "VERIFIED"
                                    ? "default"
                                    : doc.status === "REJECTED"
                                    ? "destructive"
                                    : "outline"
                                }
                                className="text-[10px]"
                              >
                                {doc.status}
                              </Badge>
                            </div>
                            <div className="text-[11px] text-muted-foreground mt-0.5">
                              Uploaded {new Date(doc.created_at).toLocaleDateString()}
                            </div>
                            {doc.document_url && (
                              <a
                                href={doc.document_url}
                                target="_blank"
                                rel="noreferrer"
                                className="text-[11px] text-purple-600 dark:text-purple-400 hover:underline flex items-center gap-1 mt-1"
                              >
                                View Document File <ExternalLink className="h-3 w-3" />
                              </a>
                            )}
                          </div>
                          <div className="flex items-center gap-1.5 shrink-0">
                            {doc.status !== "APPROVED" && doc.status !== "VERIFIED" && (
                              <Button
                                size="sm"
                                disabled={docActionLoading === doc.id}
                                onClick={() => handleDocVerify(doc.id, "APPROVED")}
                                className="h-7 text-xs px-2.5 bg-brand-yellow hover:bg-brand-yellow-dark text-ink gap-1"
                              >
                                <Check className="h-3 w-3" /> Approve
                              </Button>
                            )}
                            {doc.status !== "REJECTED" && (
                              <Button
                                variant="destructive"
                                size="sm"
                                disabled={docActionLoading === doc.id}
                                onClick={() => handleDocVerify(doc.id, "REJECTED")}
                                className="h-7 text-xs px-2.5 gap-1"
                              >
                                <Ban className="h-3 w-3" /> Reject
                              </Button>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Verification History Audit Trail */}
                <div className="space-y-3">
                  <h3 className="text-sm font-bold tracking-tight text-foreground flex items-center gap-2">
                    <Clock className="h-4 w-4 text-purple-600" />
                    Verification History & Audit Log ({retailerDetail.verification_history.length})
                  </h3>
                  {retailerDetail.verification_history.length === 0 ? (
                    <p className="text-xs text-muted-foreground italic bg-muted/20 p-4 rounded-lg">
                      No status transitions recorded for this retailer yet.
                    </p>
                  ) : (
                    <div className="border rounded-xl divide-y text-xs overflow-hidden">
                      {retailerDetail.verification_history.map((h) => (
                        <div key={h.id} className="p-3 bg-card flex flex-col sm:flex-row justify-between gap-1">
                          <div>
                            <div className="font-semibold text-foreground">
                              {h.action}: <span className="text-muted-foreground font-normal">{h.from_status} → {h.to_status}</span>
                            </div>
                            {h.reason && (
                              <div className="text-muted-foreground text-[11px] mt-0.5">
                                Reason: {h.reason}
                              </div>
                            )}
                          </div>
                          <div className="text-muted-foreground text-[11px] shrink-0 text-right">
                            {new Date(h.created_at).toLocaleString()}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Footer Controls */}
                <div className="flex items-center justify-between border-t pt-4">
                  <div className="flex gap-2">
                    {retailerDetail.verification_status !== "VERIFIED" && (
                      <Button
                        size="sm"
                        onClick={() =>
                          setActionModal({
                            isOpen: true,
                            retailerId: retailerDetail.id,
                            retailerName: retailerDetail.name,
                            targetStatus: "VERIFIED",
                            reason: "",
                          })
                        }
                        className="bg-brand-yellow hover:bg-brand-yellow-dark text-ink text-xs gap-1"
                      >
                        <ShieldCheck className="h-3.5 w-3.5" /> Approve Retailer
                      </Button>
                    )}
                    {retailerDetail.verification_status !== "REJECTED" && (
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() =>
                          setActionModal({
                            isOpen: true,
                            retailerId: retailerDetail.id,
                            retailerName: retailerDetail.name,
                            targetStatus: "REJECTED",
                            reason: "",
                          })
                        }
                        className="text-xs gap-1"
                      >
                        <Ban className="h-3.5 w-3.5" /> Reject Retailer
                      </Button>
                    )}
                    {retailerDetail.verification_status === "VERIFIED" && (
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() =>
                          setActionModal({
                            isOpen: true,
                            retailerId: retailerDetail.id,
                            retailerName: retailerDetail.name,
                            targetStatus: "SUSPENDED",
                            reason: "",
                          })
                        }
                        className="text-xs gap-1"
                      >
                        <ShieldAlert className="h-3.5 w-3.5" /> Suspend Retailer
                      </Button>
                    )}
                  </div>
                  <Button variant="outline" size="sm" onClick={closeInspection}>
                    Close
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Status Decision Modal */}
      {actionModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
          <div className="bg-card border rounded-2xl w-full max-w-md shadow-2xl p-6 space-y-4">
            <h3 className="text-lg font-bold text-foreground">
              Confirm Status Update: {actionModal.targetStatus}
            </h3>
            <p className="text-xs text-muted-foreground">
              You are updating the verification status of{" "}
              <strong className="text-foreground">{actionModal.retailerName}</strong> to{" "}
              <Badge className="ml-1 uppercase text-xs">{actionModal.targetStatus}</Badge>.
            </p>

            <div>
              <label className="text-xs font-semibold text-muted-foreground block mb-1">
                Decision Notes / Reason (Audit Log)
              </label>
              <textarea
                rows={3}
                placeholder="Enter regulatory verification notes, document checklist, or suspension grounds..."
                value={actionModal.reason}
                onChange={(e) =>
                  setActionModal({ ...actionModal, reason: e.target.value })
                }
                className="w-full text-xs rounded-lg border bg-background p-2.5 outline-hidden focus:ring-2 focus:ring-purple-500"
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setActionModal(null)}
                disabled={actionLoading}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handleStatusSubmit}
                disabled={actionLoading}
                className={
                  actionModal.targetStatus === "VERIFIED"
                    ? "bg-brand-yellow hover:bg-brand-yellow-dark text-ink"
                    : "bg-red-600 hover:bg-red-700 text-white"
                }
              >
                {actionLoading ? "Updating..." : `Confirm ${actionModal.targetStatus}`}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
