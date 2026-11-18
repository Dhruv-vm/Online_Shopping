"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Clock,
  HelpCircle,
  Loader2,
  RefreshCw,
  ShieldCheck,
  ShoppingBag,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { RazorpayPaymentButton } from "@/components/checkout/razorpay-modal";
import { createOrder, getOrder } from "@/lib/api/orders";
import { formatPrice } from "@/lib/utils";
import type { Order, PaymentVerifyResponse } from "@/types";

function CheckoutContent() {
  const searchParams = useSearchParams();
  const reservationIdParam = searchParams.get("reservation_id");
  const orderIdParam = searchParams.get("order_id");

  const [order, setOrder] = useState<Order | null>(null);
  const [isLoadingOrder, setIsLoadingOrder] = useState(false);
  const [isCreatingOrder, setIsCreatingOrder] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Payment UI states
  const [verifyResponse, setVerifyResponse] = useState<PaymentVerifyResponse | null>(null);
  const [isPolling, setIsPolling] = useState(false);
  const [pollAttempt, setPollAttempt] = useState(0);
  const [ambiguousState, setAmbiguousState] = useState(false);

  // Address state for new order creation
  const [addressId, setAddressId] = useState("");

  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);

  const fetchOrderDetails = useCallback(async (orderId: string): Promise<Order | null> => {
    try {
      const fetched = await getOrder(orderId);
      setOrder(fetched);
      if (fetched.status === "CONFIRMED") {
        setAmbiguousState(false);
      } else if (fetched.payment_status === "REQUIRES_RECONCILIATION") {
        setAmbiguousState(true);
      }
      return fetched;
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load order details.");
      return null;
    }
  }, []);

  // Initialize from query parameters
  useEffect(() => {
    if (orderIdParam) {
      setIsLoadingOrder(true);
      fetchOrderDetails(orderIdParam).finally(() => setIsLoadingOrder(false));
    }
  }, [orderIdParam, fetchOrderDetails]);

  // Clean up polling timer on unmount
  useEffect(() => {
    return () => {
      if (pollTimerRef.current) {
        clearTimeout(pollTimerRef.current);
      }
    };
  }, []);

  // Server-authoritative polling fallback after ambiguous outcome or modal dismissal
  const startPollingFallback = useCallback(() => {
    if (!order) return;
    setIsPolling(true);
    setPollAttempt(0);

    let attempts = 0;
    const maxAttempts = 5;
    const pollIntervalMs = 2500;

    const poll = async () => {
      attempts += 1;
      setPollAttempt(attempts);

      const latest = await fetchOrderDetails(order.id);
      if (latest) {
        if (latest.status === "CONFIRMED") {
          setIsPolling(false);
          return;
        }
        if (latest.payment_status === "REQUIRES_RECONCILIATION") {
          setIsPolling(false);
          setAmbiguousState(true);
          return;
        }
        if (latest.status === "CANCELLED") {
          setIsPolling(false);
          return;
        }
      }

      if (attempts < maxAttempts) {
        pollTimerRef.current = setTimeout(poll, pollIntervalMs);
      } else {
        setIsPolling(false);
      }
    };

    pollTimerRef.current = setTimeout(poll, 1500);
  }, [order, fetchOrderDetails]);

  const handleCreateOrder = async () => {
    if (!reservationIdParam) {
      setError("No active inventory reservation found.");
      return;
    }
    setIsCreatingOrder(true);
    setError(null);
    try {
      const created = await createOrder({
        reservation_id: reservationIdParam,
        delivery_address_id: addressId.trim() || undefined,
      });
      setOrder(created);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create order from reservation.");
    } finally {
      setIsCreatingOrder(false);
    }
  };

  const handlePaymentSuccess = (result: PaymentVerifyResponse) => {
    setVerifyResponse(result);
    setAmbiguousState(false);
    if (order) {
      setOrder({
        ...order,
        status: result.status,
        payment_status: result.payment_status,
        fulfilling_capture_id: result.fulfilling_capture_id,
      });
    }
  };

  const handlePaymentError = (err: Error) => {
    setError(err.message || "Payment verification failed");
    // Immediately start server-side status refresh in case gateway completed asynchronously
    startPollingFallback();
  };

  return (
    <div className="container max-w-4xl py-8 px-4 sm:px-6">
      <div className="mb-6 flex items-center justify-between border-b pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <ShoppingBag className="h-6 w-6 text-emerald-600" />
            Checkout & Order Payment
          </h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Phase 2F Razorpay sandbox gateway integration with server-side capture verification.
          </p>
        </div>
        <Link href="/cart">
          <Button variant="ghost" size="sm" className="text-xs">
            Return to Cart
          </Button>
        </Link>
      </div>

      {error && (
        <div className="mb-6 p-3.5 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-300 flex items-start gap-2.5">
          <AlertCircle className="h-5 w-5 text-red-600 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <p className="font-semibold">Checkout Notice</p>
            <p className="text-xs">{error}</p>
          </div>
        </div>
      )}

      {/* Ambiguous Reconciliation Warning */}
      {ambiguousState && (
        <div className="mb-6 p-4 bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-800 rounded-lg text-sm text-amber-900 dark:text-amber-200 flex items-start gap-3">
          <HelpCircle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
          <div className="space-y-1.5 flex-1">
            <p className="font-semibold">Payment Under Verification (Requires Reconciliation)</p>
            <p className="text-xs text-amber-800 dark:text-amber-300 leading-relaxed">
              We received your payment initiation, but gateway confirmation is currently ambiguous.
              Our automated reconciliation service is verifying the status. Please do NOT re-submit payment;
              duplicate charges are strictly prevented.
            </p>
            <Button
              size="sm"
              variant="outline"
              className="text-xs h-7 border-amber-400 text-amber-900 dark:text-amber-100 hover:bg-amber-100 dark:hover:bg-amber-900"
              onClick={() => order && fetchOrderDetails(order.id)}
            >
              <RefreshCw className="h-3.5 w-3.5 mr-1" />
              Check Status Now
            </Button>
          </div>
        </div>
      )}

      {/* Confirmed Success State */}
      {(order?.status === "CONFIRMED" || verifyResponse?.status === "CONFIRMED") && (
        <Card className="mb-6 border-emerald-500 bg-emerald-50/50 dark:bg-emerald-950/20 shadow-sm">
          <CardContent className="pt-6 space-y-4">
            <div className="flex items-center gap-3">
              <CheckCircle2 className="h-8 w-8 text-emerald-600" />
              <div>
                <h2 className="text-lg font-bold text-emerald-900 dark:text-emerald-200">
                  Payment Verified & Order Confirmed!
                </h2>
                <p className="text-xs text-emerald-700 dark:text-emerald-300">
                  Order Number: <span className="font-mono font-semibold">{order?.order_number}</span>
                </p>
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs bg-white dark:bg-zinc-900 p-3.5 rounded-md border border-emerald-200 dark:border-emerald-900">
              <div>
                <span className="text-muted-foreground">Fulfilling Capture ID:</span>
                <p className="font-mono text-[11px] truncate">
                  {order?.fulfilling_capture_id || verifyResponse?.fulfilling_capture_id || "Recorded in Ledger"}
                </p>
              </div>
              <div>
                <span className="text-muted-foreground">Amount Paid:</span>
                <p className="font-semibold text-emerald-700 dark:text-emerald-400">
                  {formatPrice(order?.total_payable_paise ?? verifyResponse?.amount_paid_paise ?? 0)}
                </p>
              </div>
            </div>
            <div className="flex justify-end pt-2">
              <Link href="/account">
                <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs">
                  View My Orders
                  <ArrowRight className="h-3.5 w-3.5 ml-1.5" />
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 1: Create Order from Reservation if no active order */}
      {!order && reservationIdParam && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Clock className="h-4 w-4 text-emerald-600" />
              Step 1: Convert Held Stock to BASKET Order
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-xs text-muted-foreground">
              Your inventory is currently locked in PostgreSQL. Provide your delivery address ID (optional) to construct an immutable order snapshot.
            </p>
            <div className="space-y-2">
              <label htmlFor="addressId" className="text-xs font-medium text-foreground">
                Delivery Address ID (Optional for Guest/Sandbox)
              </label>
              <input
                id="addressId"
                type="text"
                placeholder="e.g. 550e8400-e29b-41d4-a716-446655440000"
                value={addressId}
                onChange={(e) => setAddressId(e.target.value)}
                className="w-full text-xs p-2.5 rounded-md border bg-background font-mono focus:outline-none focus:ring-1 focus:ring-emerald-500"
              />
            </div>
            <Button
              className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs h-10"
              onClick={handleCreateOrder}
              disabled={isCreatingOrder}
            >
              {isCreatingOrder ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Creating Immutable Order...
                </>
              ) : (
                <>
                  Confirm Order & Proceed to Payment
                  <ArrowRight className="h-4 w-4 ml-2" />
                </>
              )}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Step 2: Order Summary & Authoritative Payment Initiation */}
      {order && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="md:col-span-2 space-y-4">
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">Order Details</CardTitle>
                  <div className="flex items-center gap-2">
                    <Badge variant={order.status === "CONFIRMED" ? "default" : "secondary"} className="text-[10px]">
                      {order.status}
                    </Badge>
                    <Badge variant="outline" className="text-[10px] font-mono">
                      {order.payment_status}
                    </Badge>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-3 text-xs">
                <div className="flex justify-between py-1.5 border-b">
                  <span className="text-muted-foreground">Order Number:</span>
                  <span className="font-mono font-medium">{order.order_number}</span>
                </div>
                <div className="flex justify-between py-1.5 border-b">
                  <span className="text-muted-foreground">Order ID:</span>
                  <span className="font-mono text-[11px] truncate max-w-[200px]">{order.id}</span>
                </div>
                <div className="flex justify-between py-1.5 border-b">
                  <span className="text-muted-foreground">Items in Order:</span>
                  <span>{order.items?.length ?? 1} item(s)</span>
                </div>
                <div className="flex justify-between py-1.5 border-b">
                  <span className="text-muted-foreground">Currency:</span>
                  <span className="font-semibold">{order.currency}</span>
                </div>
              </CardContent>
            </Card>

            {/* Server-Side Polling State Indicator */}
            {isPolling && (
              <div className="p-3 bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 rounded-lg text-xs text-blue-700 dark:text-blue-300 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
                  <span>Polling server for payment confirmation (attempt {pollAttempt}/5)...</span>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-xs h-6 px-2 text-blue-800"
                  onClick={() => fetchOrderDetails(order.id)}
                >
                  Refresh
                </Button>
              </div>
            )}
          </div>

          <div className="space-y-4">
            <Card className="border shadow-sm">
              <CardHeader className="pb-3 border-b">
                <CardTitle className="text-sm font-semibold">Payment Summary</CardTitle>
              </CardHeader>
              <CardContent className="pt-4 space-y-4">
                <div className="space-y-2">
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>Subtotal:</span>
                    <span>{formatPrice(order.subtotal_paise ?? order.total_payable_paise)}</span>
                  </div>
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>GST (Tax):</span>
                    <span>{formatPrice(order.total_tax_paise ?? 0)}</span>
                  </div>
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>Delivery:</span>
                    <span>{formatPrice(order.delivery_fee_paise ?? 0)}</span>
                  </div>
                  <div className="pt-2 border-t flex justify-between text-sm font-bold text-foreground">
                    <span>Total Authoritative:</span>
                    <span className="text-emerald-700 dark:text-emerald-400">
                      {formatPrice(order.total_payable_paise)}
                    </span>
                  </div>
                </div>

                {/* Gateway Payment Button */}
                {order.status === "PENDING_PAYMENT" && (
                  <div className="pt-2">
                    <RazorpayPaymentButton
                      orderId={order.id}
                      amountPaise={order.total_payable_paise}
                      currency={order.currency}
                      disabled={isPolling || isLoadingOrder}
                      className="w-full bg-slate-900 hover:bg-slate-800 text-white font-semibold text-xs h-11 shadow-sm"
                      onSuccess={handlePaymentSuccess}
                      onError={handlePaymentError}
                      onDismissOrAmbiguous={startPollingFallback}
                    />
                    <p className="text-[10px] text-center text-muted-foreground mt-2">
                      Secured by Razorpay Sandbox & HMAC-SHA256 signature verification
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Invariant Guarantees */}
            <div className="p-3 bg-muted/40 rounded-lg border text-[11px] text-muted-foreground space-y-1.5">
              <div className="flex items-center gap-1.5 text-emerald-700 dark:text-emerald-400 font-medium">
                <ShieldCheck className="h-3.5 w-3.5 shrink-0" />
                <span>Zero Frontend-Trusted Amounts</span>
              </div>
              <p className="text-[10px] leading-relaxed">
                Payment attempts and gateway orders are durably created by PostgreSQL before checkout modal opens.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function CheckoutPage() {
  return (
    <React.Suspense
      fallback={
        <div className="container max-w-4xl py-12 flex justify-center items-center">
          <Loader2 className="h-6 w-6 animate-spin text-emerald-600" />
        </div>
      }
    >
      <CheckoutContent />
    </React.Suspense>
  );
}
