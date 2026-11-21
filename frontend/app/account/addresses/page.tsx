"use client";

import React, { useState, useEffect, useCallback } from "react";
import { apiClient, ApiClientError } from "@/lib/api/client";
import { ProtectedRoute } from "@/components/auth/protected-route";
import { AccountNav } from "@/components/account/account-nav";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import type { Address, AddressCreatePayload, AddressUpdatePayload } from "@/types";
import {
  MapPin,
  Plus,
  Trash2,
  Edit2,
  Check,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Home,
  Phone,
  User,
  Star,
  X,
} from "lucide-react";

const INDIAN_STATES = [
  "Andhra Pradesh",
  "Arunachal Pradesh",
  "Assam",
  "Bihar",
  "Chhattisgarh",
  "Goa",
  "Gujarat",
  "Haryana",
  "Himachal Pradesh",
  "Jharkhand",
  "Karnataka",
  "Kerala",
  "Madhya Pradesh",
  "Maharashtra",
  "Manipur",
  "Meghalaya",
  "Mizoram",
  "Nagaland",
  "Odisha",
  "Punjab",
  "Rajasthan",
  "Sikkim",
  "Tamil Nadu",
  "Telangana",
  "Tripura",
  "Uttar Pradesh",
  "Uttarakhand",
  "West Bengal",
  "Andaman and Nicobar Islands",
  "Chandigarh",
  "Dadra and Nagar Haveli and Daman and Diu",
  "Delhi",
  "Jammu and Kashmir",
  "Ladakh",
  "Lakshadweep",
  "Puducherry",
];

export default function AddressesPage() {
  const [addresses, setAddresses] = useState<Address[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [actionId, setActionId] = useState<string | null>(null);

  const [formOpen, setFormOpen] = useState(false);
  const [editingAddress, setEditingAddress] = useState<Address | null>(null);

  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(
    null
  );

  // Form State
  const [recipientName, setRecipientName] = useState("");
  const [phone, setPhone] = useState("");
  const [line1, setLine1] = useState("");
  const [line2, setLine2] = useState("");
  const [city, setCity] = useState("");
  const [stateName, setStateName] = useState("Karnataka");
  const [postalCode, setPostalCode] = useState("");
  const [landmark, setLandmark] = useState("");
  const [isDefault, setIsDefault] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const loadAddresses = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await apiClient.getAddresses();
      setAddresses(data);
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setFeedback({ type: "error", message: err.message });
      } else {
        setFeedback({ type: "error", message: "Failed to load saved addresses." });
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAddresses();
  }, [loadAddresses]);

  const resetForm = () => {
    setRecipientName("");
    setPhone("");
    setLine1("");
    setLine2("");
    setCity("");
    setStateName("Karnataka");
    setPostalCode("");
    setLandmark("");
    setIsDefault(false);
    setEditingAddress(null);
    setFormError(null);
    setFormOpen(false);
  };

  const openAddForm = () => {
    resetForm();
    setIsDefault(addresses.length === 0);
    setFormOpen(true);
  };

  const openEditForm = (addr: Address) => {
    setEditingAddress(addr);
    setRecipientName(addr.recipient_name);
    setPhone(addr.phone);
    setLine1(addr.line1);
    setLine2(addr.line2 || "");
    setCity(addr.city);
    setStateName(addr.state);
    setPostalCode(addr.postal_code);
    setLandmark(addr.landmark || "");
    setIsDefault(addr.is_default);
    setFormError(null);
    setFormOpen(true);
  };

  const validateForm = (): boolean => {
    if (!recipientName.trim() || recipientName.trim().length < 2) {
      setFormError("Please enter recipient name (at least 2 characters).");
      return false;
    }

    const cleanPhone = phone.trim();
    if (!cleanPhone || cleanPhone.length < 10) {
      setFormError("Please enter a valid 10-digit mobile number.");
      return false;
    }

    if (!line1.trim() || line1.trim().length < 3) {
      setFormError("Please enter address line 1 (street, building, or area).");
      return false;
    }

    if (!city.trim() || city.trim().length < 2) {
      setFormError("Please enter city name.");
      return false;
    }

    const cleanPin = postalCode.trim();
    if (!/^[1-9][0-9]{5}$/.test(cleanPin)) {
      setFormError("Please enter a valid 6-digit Indian PIN code (e.g. 560001).");
      return false;
    }

    setFormError(null);
    return true;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;

    setIsSubmitting(true);
    setFeedback(null);

    try {
      if (editingAddress) {
        // Edit existing address
        const updatePayload: AddressUpdatePayload = {
          recipient_name: recipientName.trim(),
          phone: phone.trim(),
          line1: line1.trim(),
          line2: line2.trim() || null,
          city: city.trim(),
          state: stateName.trim(),
          postal_code: postalCode.trim(),
          landmark: landmark.trim() || null,
          is_default: isDefault,
        };

        const updated = await apiClient.updateAddress(editingAddress.id, updatePayload);
        setFeedback({
          type: "success",
          message: `Address for "${updated.recipient_name}" updated successfully.`,
        });
      } else {
        // Create new address
        const createPayload: AddressCreatePayload = {
          recipient_name: recipientName.trim(),
          phone: phone.trim(),
          line1: line1.trim(),
          line2: line2.trim() || null,
          city: city.trim(),
          state: stateName.trim(),
          postal_code: postalCode.trim(),
          landmark: landmark.trim() || null,
          is_default: isDefault || addresses.length === 0,
        };

        const created = await apiClient.createAddress(createPayload);
        setFeedback({
          type: "success",
          message: `New address for "${created.recipient_name}" added successfully.`,
        });
      }

      resetForm();
      await loadAddresses();
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setFormError(err.message || "Failed to save address.");
      } else {
        setFormError("Network error: Unable to save address.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSetDefault = async (addr: Address) => {
    if (addr.is_default) return;
    setActionId(addr.id);
    setFeedback(null);

    try {
      await apiClient.updateAddress(addr.id, { is_default: true });
      setFeedback({
        type: "success",
        message: `Set "${addr.recipient_name}" as your default delivery address.`,
      });
      await loadAddresses();
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setFeedback({ type: "error", message: err.message });
      } else {
        setFeedback({ type: "error", message: "Failed to update default address." });
      }
    } finally {
      setActionId(null);
    }
  };

  const handleDelete = async (addr: Address) => {
    if (
      !window.confirm(
        `Are you sure you want to delete the address for "${addr.recipient_name}"?`
      )
    ) {
      return;
    }

    setActionId(addr.id);
    setFeedback(null);

    try {
      await apiClient.deleteAddress(addr.id);
      setFeedback({
        type: "success",
        message: `Address for "${addr.recipient_name}" deleted.`,
      });
      await loadAddresses();
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setFeedback({ type: "error", message: err.message });
      } else {
        setFeedback({ type: "error", message: "Failed to delete address." });
      }
    } finally {
      setActionId(null);
    }
  };

  return (
    <ProtectedRoute>
      <div className="container mx-auto px-4 py-8 sm:py-12 max-w-6xl">
        <div className="flex flex-col md:flex-row gap-8 items-start">
          <AccountNav />

          <main className="flex-1 w-full space-y-6">
            {/* Page Header */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b pb-5">
              <div>
                <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
                  <MapPin className="h-6 w-6 text-emerald-600" />
                  Address Book
                </h1>
                <p className="text-sm text-muted-foreground mt-1">
                  Manage delivery addresses for seamless checkout across all partner retailers.
                </p>
              </div>

              {!formOpen && (
                <Button
                  onClick={openAddForm}
                  className="bg-brand-yellow hover:bg-brand-yellow-dark text-ink font-medium shadow-sm transition-colors shrink-0"
                >
                  <Plus className="mr-1.5 h-4 w-4" /> Add New Address
                </Button>
              )}
            </div>

            {/* Global Feedback Banner */}
            {feedback && (
              <div
                role="alert"
                className={`flex items-center gap-3 rounded-xl border p-4 text-sm font-medium ${
                  feedback.type === "success"
                    ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300"
                    : "border-red-500/20 bg-red-500/10 text-red-800 dark:text-red-300"
                }`}
              >
                {feedback.type === "success" ? (
                  <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-600 dark:text-emerald-400" />
                ) : (
                  <AlertCircle className="h-5 w-5 shrink-0 text-red-600 dark:text-red-400" />
                )}
                <span>{feedback.message}</span>
                <button
                  type="button"
                  onClick={() => setFeedback(null)}
                  className="ml-auto text-muted-foreground hover:text-foreground"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            )}

            {/* Inline Address Form (Add / Edit) */}
            {formOpen && (
              <Card className="border-emerald-600/40 shadow-md">
                <CardHeader className="pb-4 border-b">
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="text-lg font-bold">
                        {editingAddress ? "Edit Delivery Address" : "Add New Delivery Address"}
                      </CardTitle>
                      <CardDescription>
                        All fields marked with an asterisk are required
                      </CardDescription>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={resetForm}
                      className="h-8 w-8 p-0"
                      aria-label="Close form"
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                </CardHeader>

                <CardContent className="pt-6">
                  {formError && (
                    <div
                      role="alert"
                      className="mb-6 flex items-start gap-2.5 rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-700 dark:text-red-400 font-medium"
                    >
                      <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                      <span>{formError}</span>
                    </div>
                  )}

                  <form onSubmit={handleSubmit} className="space-y-4">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div className="space-y-1.5">
                        <label
                          htmlFor="recipient_name"
                          className="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
                        >
                          Recipient Full Name *
                        </label>
                        <Input
                          id="recipient_name"
                          required
                          placeholder="e.g. Rahul Sharma"
                          value={recipientName}
                          onChange={(e) => setRecipientName(e.target.value)}
                          disabled={isSubmitting}
                        />
                      </div>

                      <div className="space-y-1.5">
                        <label
                          htmlFor="addr_phone"
                          className="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
                        >
                          10-Digit Mobile Phone *
                        </label>
                        <Input
                          id="addr_phone"
                          type="tel"
                          required
                          placeholder="+91 98765 43210"
                          value={phone}
                          onChange={(e) => setPhone(e.target.value)}
                          disabled={isSubmitting}
                        />
                      </div>
                    </div>

                    <div className="space-y-1.5">
                      <label
                        htmlFor="line1"
                        className="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
                      >
                        Flat / House No., Apartment, Street *
                      </label>
                      <Input
                        id="line1"
                        required
                        placeholder="e.g. Flat 402, Sunshine Heights, 12th Main Road"
                        value={line1}
                        onChange={(e) => setLine1(e.target.value)}
                        disabled={isSubmitting}
                      />
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div className="space-y-1.5">
                        <label
                          htmlFor="line2"
                          className="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
                        >
                          Area / Colony (Optional)
                        </label>
                        <Input
                          id="line2"
                          placeholder="e.g. Indiranagar Stage 2"
                          value={line2}
                          onChange={(e) => setLine2(e.target.value)}
                          disabled={isSubmitting}
                        />
                      </div>

                      <div className="space-y-1.5">
                        <label
                          htmlFor="landmark"
                          className="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
                        >
                          Landmark (Optional)
                        </label>
                        <Input
                          id="landmark"
                          placeholder="e.g. Opposite BDA Complex"
                          value={landmark}
                          onChange={(e) => setLandmark(e.target.value)}
                          disabled={isSubmitting}
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                      <div className="space-y-1.5">
                        <label
                          htmlFor="city"
                          className="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
                        >
                          City / Town *
                        </label>
                        <Input
                          id="city"
                          required
                          placeholder="e.g. Bengaluru"
                          value={city}
                          onChange={(e) => setCity(e.target.value)}
                          disabled={isSubmitting}
                        />
                      </div>

                      <div className="space-y-1.5">
                        <label
                          htmlFor="state"
                          className="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
                        >
                          State / Union Territory *
                        </label>
                        <select
                          id="state"
                          value={stateName}
                          onChange={(e) => setStateName(e.target.value)}
                          disabled={isSubmitting}
                          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {INDIAN_STATES.map((st) => (
                            <option key={st} value={st}>
                              {st}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div className="space-y-1.5">
                        <label
                          htmlFor="postal_code"
                          className="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
                        >
                          6-Digit PIN Code *
                        </label>
                        <Input
                          id="postal_code"
                          required
                          maxLength={6}
                          placeholder="e.g. 560001"
                          value={postalCode}
                          onChange={(e) => setPostalCode(e.target.value.replace(/\D/g, ""))}
                          disabled={isSubmitting}
                        />
                      </div>
                    </div>

                    <div className="pt-2">
                      <label className="flex items-center gap-2.5 cursor-pointer text-sm font-medium text-foreground">
                        <input
                          type="checkbox"
                          checked={isDefault}
                          onChange={(e) => setIsDefault(e.target.checked)}
                          disabled={isSubmitting || (editingAddress?.is_default && addresses.length === 1)}
                          className="h-4 w-4 rounded border-gray-300 text-emerald-600 focus:ring-emerald-600"
                        />
                        <span>Make this my default delivery address</span>
                      </label>
                    </div>

                    <div className="flex items-center justify-end gap-3 pt-4 border-t">
                      <Button
                        type="button"
                        variant="outline"
                        onClick={resetForm}
                        disabled={isSubmitting}
                      >
                        Cancel
                      </Button>
                      <Button
                        type="submit"
                        disabled={isSubmitting}
                        className="bg-brand-yellow hover:bg-brand-yellow-dark text-ink font-medium"
                      >
                        {isSubmitting ? (
                          <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            Saving Address...
                          </>
                        ) : editingAddress ? (
                          "Update Address"
                        ) : (
                          "Save Address"
                        )}
                      </Button>
                    </div>
                  </form>
                </CardContent>
              </Card>
            )}

            {/* Loading Skeletons */}
            {isLoading && (
              <div className="grid grid-cols-1 gap-4">
                {[1, 2].map((i) => (
                  <Card key={i} className="animate-pulse">
                    <CardContent className="p-6 space-y-3">
                      <div className="h-5 bg-muted rounded w-1/4" />
                      <div className="h-4 bg-muted rounded w-3/4" />
                      <div className="h-4 bg-muted rounded w-1/2" />
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}

            {/* Empty Address State */}
            {!isLoading && addresses.length === 0 && !formOpen && (
              <Card className="border-dashed border-2 py-12 text-center">
                <CardContent className="flex flex-col items-center justify-center space-y-4">
                  <div className="p-4 rounded-full bg-emerald-50 text-emerald-600 dark:bg-emerald-950/60 dark:text-emerald-400">
                    <Home className="h-8 w-8" />
                  </div>
                  <div className="space-y-1 max-w-sm">
                    <h3 className="font-bold text-lg text-foreground">No Saved Addresses</h3>
                    <p className="text-sm text-muted-foreground">
                      You haven&apos;t added any delivery addresses yet. Add one now for instant checkout.
                    </p>
                  </div>
                  <Button
                    onClick={openAddForm}
                    className="bg-brand-yellow hover:bg-brand-yellow-dark text-ink font-medium mt-2"
                  >
                    <Plus className="mr-1.5 h-4 w-4" /> Add Your First Address
                  </Button>
                </CardContent>
              </Card>
            )}

            {/* Address List */}
            {!isLoading && addresses.length > 0 && (
              <div className="grid grid-cols-1 gap-4">
                {addresses.map((addr) => {
                  const isProcessing = actionId === addr.id;

                  return (
                    <Card
                      key={addr.id}
                      className={`relative transition-all ${
                        addr.is_default
                          ? "border-emerald-600/60 shadow-sm bg-card"
                          : "hover:border-muted-foreground/30"
                      }`}
                    >
                      <CardContent className="p-5 sm:p-6">
                        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                          <div className="space-y-1.5 flex-1">
                            <div className="flex flex-wrap items-center gap-2.5">
                              <span className="font-bold text-base text-foreground flex items-center gap-1.5">
                                <User className="h-4 w-4 text-emerald-600 shrink-0" />
                                {addr.recipient_name}
                              </span>

                              {addr.is_default && (
                                <Badge className="bg-emerald-600 text-white font-semibold text-xs py-0.5 px-2">
                                  <Star className="h-3 w-3 mr-1 fill-white" /> Default Address
                                </Badge>
                              )}
                            </div>

                            <p className="text-sm text-foreground/90 font-medium">
                              {addr.line1}
                              {addr.line2 ? `, ${addr.line2}` : ""}
                            </p>

                            <p className="text-sm text-muted-foreground">
                              {addr.city}, {addr.state} — <span className="font-semibold text-foreground">{addr.postal_code}</span>
                            </p>

                            {addr.landmark && (
                              <p className="text-xs text-muted-foreground">
                                Landmark: {addr.landmark}
                              </p>
                            )}

                            <p className="text-xs text-muted-foreground flex items-center gap-1 pt-1">
                              <Phone className="h-3.5 w-3.5 text-muted-foreground" />
                              Phone: <span className="text-foreground font-medium">{addr.phone}</span>
                            </p>
                          </div>

                          {/* Action Buttons */}
                          <div className="flex flex-wrap sm:flex-col items-center sm:items-end gap-2 shrink-0 pt-2 sm:pt-0 border-t sm:border-t-0 border-muted/50">
                            {!addr.is_default && (
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleSetDefault(addr)}
                                disabled={isProcessing || isSubmitting}
                                className="h-8 text-xs font-medium border-emerald-600/30 text-emerald-700 hover:bg-emerald-50 dark:text-emerald-400 dark:hover:bg-emerald-950/40"
                              >
                                {isProcessing ? (
                                  <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" />
                                ) : (
                                  <Check className="h-3.5 w-3.5 mr-1" />
                                )}
                                Set as Default
                              </Button>
                            )}

                            <div className="flex items-center gap-2">
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => openEditForm(addr)}
                                disabled={isProcessing || isSubmitting}
                                className="h-8 px-2.5 text-xs text-muted-foreground hover:text-foreground"
                              >
                                <Edit2 className="h-3.5 w-3.5 mr-1" /> Edit
                              </Button>

                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleDelete(addr)}
                                disabled={isProcessing || isSubmitting}
                                className="h-8 px-2.5 text-xs text-red-600 hover:bg-red-50 hover:text-red-700 dark:text-red-400 dark:hover:bg-red-950/40 border-red-200 dark:border-red-900"
                              >
                                {isProcessing ? (
                                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                ) : (
                                  <Trash2 className="h-3.5 w-3.5 text-red-500" />
                                )}
                              </Button>
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            )}
          </main>
        </div>
      </div>
    </ProtectedRoute>
  );
}
