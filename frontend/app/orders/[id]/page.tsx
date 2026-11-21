"use client";

import { useEffect, useState, useCallback, use } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Package,
  ArrowLeft,
  Truck,
  RotateCcw,
  XCircle,
  MapPin,
  CreditCard,
  Calendar,
  AlertCircle,
  CheckCircle2,
  Clock,
  ExternalLink,
  Loader2,
  Receipt,
  ShieldCheck,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiClient } from "@/lib/api/client";
import type { Order, OrderStatus, ReturnStatus } from "@/types/index";
import { useLiveUpdates } from "@/lib/realtime";

function formatPrice(paise: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
  }).format(paise / 100);
}

function getStatusBadge(status: OrderStatus) {
  switch (status) {
    case "DELIVERED":
      return <Badge className="bg-brand-yellow text-ink hover:bg-brand-yellow-dark">Delivered</Badge>;
    case "SHIPPED":
      return <Badge className="bg-blue-600 text-white hover:bg-blue-700">Shipped</Badge>;
    case "OUT_FOR_DELIVERY":
      return <Badge className="bg-indigo-600 text-white hover:bg-indigo-700">Out for Delivery</Badge>;
    case "PACKED":
    case "PROCESSING":
      return <Badge className="bg-amber-600 text-white hover:bg-amber-700">{status}</Badge>;
    case "CONFIRMED":
      return <Badge className="bg-teal-600 text-white hover:bg-teal-700">Confirmed</Badge>;
    case "PENDING_PAYMENT":
      return <Badge variant="outline" className="text-amber-600 border-amber-500">Payment Pending</Badge>;
    case "CANCELLED":
      return <Badge variant="destructive">Cancelled</Badge>;
    case "RETURNED":
      return <Badge className="bg-purple-600 text-white hover:bg-purple-700">Returned</Badge>;
    default:
      return <Badge variant="secondary">{status}</Badge>;
  }
}

export default function OrderDetailsPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const resolvedParams = use(params);
  const orderId = resolvedParams.id;
  const accessToken = searchParams.get("access_token") || undefined;

  const [order, setOrder] = useState<Order | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Cancellation modal state
  const [cancelModalOpen, setCancelModalOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const [cancelLoading, setCancelLoading] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);

  // Return modal state
  const [returnModalOpen, setReturnModalOpen] = useState(false);
  const [returnReason, setReturnReason] = useState("");
  const [returnNotes, setReturnNotes] = useState("");
  const [selectedItemQuantities, setSelectedItemQuantities] = useState<Record<string, number>>({});
  const [returnLoading, setReturnLoading] = useState(false);
  const [returnError, setReturnError] = useState<string | null>(null);

  const fetchOrderDetails = useCallback(async (opts?: { quiet?: boolean }) => {
    if (!opts?.quiet) setLoading(true);
    setError(null);
    try {
      const data = await apiClient.getOrder(orderId, accessToken);
      setOrder(data);
      if (opts?.quiet) return;
      // Initialize return quantities
      const initialQuantities: Record<string, number> = {};
      data.items.forEach((item) => {
        initialQuantities[item.id] = 1;
      });
      setSelectedItemQuantities(initialQuantities);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load order.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [orderId, accessToken]);
  useLiveUpdates(["order.", "payment.", "fulfilment."], () => void fetchOrderDetails({ quiet: true }));

  useEffect(() => {
    fetchOrderDetails();
  }, [fetchOrderDetails]);

  const canCancel =
    order &&
    ["PENDING_PAYMENT", "CONFIRMED", "PROCESSING", "PACKED"].includes(order.status);

  const canReturn =
    order &&
    order.status === "DELIVERED" &&
    order.delivered_at &&
    new Date().getTime() - new Date(order.delivered_at).getTime() <= 15 * 24 * 60 * 60 * 1000;

  const handleCancelOrder = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!cancelReason.trim()) {
      setCancelError("Please select or enter a cancellation reason.");
      return;
    }
    setCancelLoading(true);
    setCancelError(null);
    try {
      await apiClient.cancelOrder(orderId, cancelReason.trim(), undefined, accessToken);
      setCancelModalOpen(false);
      await fetchOrderDetails();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to cancel order.";
      setCancelError(msg);
    } finally {
      setCancelLoading(false);
    }
  };

  const handleRequestReturn = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!returnReason.trim()) {
      setReturnError("Please specify a reason for return.");
      return;
    }
    const returnItems = Object.entries(selectedItemQuantities)
      .filter(([_, qty]) => qty > 0)
      .map(([itemId, qty]) => ({
        order_item_id: itemId,
        quantity: qty,
      }));

    if (returnItems.length === 0) {
      setReturnError("Please select at least one item to return.");
      return;
    }

    setReturnLoading(true);
    setReturnError(null);
    try {
      await apiClient.requestReturn(
        orderId,
        {
          reason: returnReason.trim(),
          customer_notes: returnNotes.trim() || undefined,
          items: returnItems,
        },
        undefined,
        accessToken,
      );
      setReturnModalOpen(false);
      await fetchOrderDetails();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to request return.";
      setReturnError(msg);
    } finally {
      setReturnLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-16 flex flex-col items-center justify-center text-muted-foreground">
        <Loader2 className="h-8 w-8 animate-spin text-emerald-600 mb-3" />
        <p className="text-sm font-medium">Loading order details...</p>
      </div>
    );
  }

  if (error || !order) {
    return (
      <div className="container mx-auto px-4 py-12 max-w-2xl text-center">
        <div className="p-8 rounded-xl border border-red-200 bg-red-50/50 dark:bg-red-950/20 text-red-700 dark:text-red-300 space-y-4">
          <AlertCircle className="h-10 w-10 text-red-600 mx-auto" />
          <h2 className="text-lg font-bold">Order Not Found</h2>
          <p className="text-xs">{error || "Unable to retrieve order details."}</p>
          <div className="pt-2">
            <Link href="/orders">
              <Button size="sm" variant="outline" className="text-xs">
                Back to Orders
              </Button>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const querySuffix = accessToken ? `?access_token=${encodeURIComponent(accessToken)}` : "";

  return (
    <div className="container mx-auto px-4 py-8 max-w-5xl">
      {/* Top Breadcrumb / Back button */}
      <div className="flex items-center gap-2 mb-6">
        <Link href="/orders" className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1">
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to Orders
        </Link>
      </div>

      {/* Order Header Summary Banner */}
      <div className="bg-card border rounded-xl p-5 mb-6 shadow-xs flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div className="space-y-1.5">
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-xl font-bold font-mono text-foreground">
              {order.order_number}
            </h1>
            {getStatusBadge(order.status)}
            <Badge variant="outline" className="text-xs">
              Payment: {order.payment_status}
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground flex items-center gap-1.5">
            <Calendar className="h-3.5 w-3.5" />
            Placed on{" "}
            {new Date(order.created_at).toLocaleDateString("en-IN", {
              year: "numeric",
              month: "long",
              day: "numeric",
              hour: "2-digit",
              minute: "2-digit",
            })}
          </p>
          {order.cancellation_reason && (
            <p className="text-xs text-red-600 font-medium">
              Cancellation Reason: {order.cancellation_reason}
            </p>
          )}
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center gap-2.5">
          <Link href={`/orders/${order.id}/track${querySuffix}`}>
            <Button size="sm" className="bg-brand-yellow hover:bg-brand-yellow-dark text-ink text-xs gap-1.5">
              <Truck className="h-3.5 w-3.5" />
              Track Package
            </Button>
          </Link>

          {canCancel && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => setCancelModalOpen(true)}
              className="text-xs text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950/30 border-red-200"
            >
              <XCircle className="h-3.5 w-3.5 mr-1.5" />
              Cancel Order
            </Button>
          )}

          {canReturn && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => setReturnModalOpen(true)}
              className="text-xs text-purple-600 hover:text-purple-700 hover:bg-purple-50 dark:hover:bg-purple-950/30 border-purple-200"
            >
              <RotateCcw className="h-3.5 w-3.5 mr-1.5" />
              Return Items
            </Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Items & Timeline */}
        <div className="lg:col-span-2 space-y-6">
          {/* Purchased Items Card */}
          <Card>
            <CardHeader className="py-4 px-5 border-b">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <Package className="h-4 w-4 text-emerald-600" />
                Purchased Items ({order.items.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0 divide-y divide-muted/60">
              {order.items.map((item) => (
                <div key={item.id} className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                  <div className="space-y-1">
                    <h4 className="font-semibold text-foreground text-sm">
                      {item.product_title}
                    </h4>
                    {item.variant_title && (
                      <p className="text-muted-foreground">
                        Variant: <span className="text-foreground">{item.variant_title}</span>
                      </p>
                    )}
                    <p className="text-[11px] text-muted-foreground">
                      Sold by <span className="font-medium text-foreground">{item.retailer_name}</span> ({item.retailer_state})
                      {item.hsn_code && ` • HSN: ${item.hsn_code}`}
                      {item.gst_rate_basis_points !== undefined && ` • GST: ${item.gst_rate_basis_points / 100}%`}
                    </p>
                  </div>
                  <div className="text-right sm:shrink-0">
                    <p className="font-bold text-sm text-foreground">
                      {formatPrice(item.total_selling_price_paise)}
                    </p>
                    <p className="text-[11px] text-muted-foreground">
                      {item.quantity} × {formatPrice(item.unit_discounted_price_paise)}
                    </p>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          {/* Shipments Card (if any) */}
          {order.shipments && order.shipments.length > 0 && (
            <Card>
              <CardHeader className="py-4 px-5 border-b">
                <CardTitle className="text-sm font-semibold flex items-center gap-2">
                  <Truck className="h-4 w-4 text-emerald-600" />
                  Shipment Information
                </CardTitle>
              </CardHeader>
              <CardContent className="p-5 space-y-4">
                {order.shipments.map((s) => (
                  <div key={s.id} className="p-3.5 rounded-lg border bg-muted/20 space-y-2 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-foreground">
                        Carrier: {s.carrier_name}
                      </span>
                      <Badge variant="outline" className="text-[10px]">
                        {s.status}
                      </Badge>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-muted-foreground">Tracking Number:</span>
                      <span className="font-mono font-medium text-foreground">{s.tracking_number}</span>
                      {s.tracking_url && (
                        <a
                          href={s.tracking_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-emerald-600 hover:underline flex items-center gap-1 font-medium ml-2"
                        >
                          Carrier Portal
                          <ExternalLink className="h-3 w-3" />
                        </a>
                      )}
                    </div>
                    {s.estimated_delivery_at && (
                      <p className="text-muted-foreground">
                        Est. Delivery: {new Date(s.estimated_delivery_at).toLocaleDateString("en-IN", { month: "short", day: "numeric" })}
                      </p>
                    )}
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Returns History Card (if any) */}
          {order.returns && order.returns.length > 0 && (
            <Card>
              <CardHeader className="py-4 px-5 border-b">
                <CardTitle className="text-sm font-semibold flex items-center gap-2 text-purple-700 dark:text-purple-400">
                  <RotateCcw className="h-4 w-4" />
                  Returns & Replacements
                </CardTitle>
              </CardHeader>
              <CardContent className="p-5 space-y-3">
                {order.returns.map((ret) => (
                  <div key={ret.id} className="p-3.5 rounded-lg border border-purple-200 dark:border-purple-900 bg-purple-50/30 dark:bg-purple-950/20 text-xs space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="font-mono font-semibold text-foreground">{ret.return_number}</span>
                      <Badge className="bg-purple-600 text-white text-[10px]">{ret.status}</Badge>
                    </div>
                    <p className="text-muted-foreground">
                      Reason: <span className="text-foreground">{ret.reason}</span>
                    </p>
                    <p className="text-muted-foreground">
                      Refund Value: <span className="font-semibold text-foreground">{formatPrice(ret.refund_amount_paise)}</span>
                    </p>
                    {ret.admin_notes && (
                      <p className="text-muted-foreground">
                        Admin Note: <span className="text-foreground italic">{ret.admin_notes}</span>
                      </p>
                    )}
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Order Event Timeline History */}
          {order.status_history && order.status_history.length > 0 && (
            <Card>
              <CardHeader className="py-4 px-5 border-b">
                <CardTitle className="text-sm font-semibold flex items-center gap-2">
                  <Clock className="h-4 w-4 text-emerald-600" />
                  Lifecycle History
                </CardTitle>
              </CardHeader>
              <CardContent className="p-5">
                <div className="relative pl-6 space-y-4 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-muted-foreground/20">
                  {order.status_history.map((h, i) => (
                    <div key={h.id || i} className="relative text-xs space-y-0.5">
                      <div className="absolute -left-6 top-1 h-2.5 w-2.5 rounded-full bg-emerald-600 ring-4 ring-background" />
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-foreground">{h.to_status}</span>
                        <span className="text-[10px] text-muted-foreground">
                          {new Date(h.created_at).toLocaleDateString("en-IN", {
                            month: "short",
                            day: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </span>
                      </div>
                      {h.reason && <p className="text-muted-foreground">{h.reason}</p>}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Right Column: Pricing & Delivery Address */}
        <div className="space-y-6">
          {/* Price Breakdown */}
          <Card>
            <CardHeader className="py-4 px-5 border-b">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <Receipt className="h-4 w-4 text-emerald-600" />
                Payment Summary
              </CardTitle>
            </CardHeader>
            <CardContent className="p-5 space-y-3 text-xs">
              <div className="flex justify-between text-muted-foreground">
                <span>Items Subtotal</span>
                <span>{formatPrice(order.subtotal_paise)}</span>
              </div>
              {order.discount_total_paise > 0 && (
                <div className="flex justify-between text-emerald-600 font-medium">
                  <span>Discounts</span>
                  <span>-{formatPrice(order.discount_total_paise)}</span>
                </div>
              )}
              <div className="flex justify-between text-muted-foreground">
                <span>Delivery Fee</span>
                <span>{order.delivery_fee_paise === 0 ? "FREE" : formatPrice(order.delivery_fee_paise)}</span>
              </div>
              <div className="flex justify-between text-muted-foreground">
                <span>Taxes (GST)</span>
                <span>{formatPrice(order.total_tax_paise)}</span>
              </div>
              <div className="pt-2 border-t flex justify-between font-bold text-sm text-foreground">
                <span>Total Amount</span>
                <span>{formatPrice(order.total_payable_paise)}</span>
              </div>
            </CardContent>
          </Card>

          {/* Delivery Address Card */}
          <Card>
            <CardHeader className="py-4 px-5 border-b">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <MapPin className="h-4 w-4 text-emerald-600" />
                Delivery Address
              </CardTitle>
            </CardHeader>
            <CardContent className="p-5 text-xs space-y-1.5 text-muted-foreground">
              <p className="font-semibold text-foreground text-sm">
                {order.delivery_address?.full_name}
              </p>
              <p>{order.delivery_address?.address_line1}</p>
              {order.delivery_address?.address_line2 && (
                <p>{order.delivery_address.address_line2}</p>
              )}
              <p>
                {order.delivery_address?.city}, {order.delivery_address?.state} {order.delivery_address?.postal_code}
              </p>
              <p className="pt-1 text-foreground font-mono">
                Phone: {order.delivery_address?.phone}
              </p>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Cancellation Modal Dialog */}
      {cancelModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
          <div className="bg-card border rounded-xl max-w-md w-full p-6 shadow-2xl space-y-4 text-card-foreground">
            <h3 className="text-lg font-bold text-foreground flex items-center gap-2">
              <XCircle className="h-5 w-5 text-red-600" />
              Cancel Order
            </h3>
            <p className="text-xs text-muted-foreground">
              Are you sure you want to cancel Order #{order.order_number}? Unpaid reservations will be released, and captured payments will be refunded to your source account.
            </p>

            <form onSubmit={handleCancelOrder} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-foreground">
                  Reason for Cancellation
                </label>
                <select
                  value={cancelReason}
                  onChange={(e) => setCancelReason(e.target.value)}
                  className="w-full h-9 text-xs p-2 rounded-md border bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500"
                >
                  <option value="">Select a reason...</option>
                  <option value="Customer changed mind">Customer changed mind</option>
                  <option value="Incorrect shipping address">Incorrect shipping address</option>
                  <option value="Ordered by mistake">Ordered by mistake</option>
                  <option value="Found cheaper elsewhere">Found cheaper elsewhere</option>
                  <option value="Delivery delayed">Delivery delayed</option>
                </select>
              </div>

              {cancelError && <p className="text-xs text-red-600 font-medium">{cancelError}</p>}

              <div className="flex justify-end gap-2.5 pt-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setCancelModalOpen(false)}
                  disabled={cancelLoading}
                  className="text-xs"
                >
                  Keep Order
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  variant="destructive"
                  disabled={cancelLoading}
                  className="text-xs"
                >
                  {cancelLoading ? "Cancelling..." : "Confirm Cancellation"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Return Request Modal Dialog */}
      {returnModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
          <div className="bg-card border rounded-xl max-w-lg w-full p-6 shadow-2xl space-y-4 text-card-foreground max-h-[90vh] overflow-y-auto">
            <h3 className="text-lg font-bold text-foreground flex items-center gap-2">
              <RotateCcw className="h-5 w-5 text-purple-600" />
              Request a Return
            </h3>
            <p className="text-xs text-muted-foreground">
              Select the items you wish to return under BASKET’s 15-day return policy. Items will be inspected upon receipt and refunded to your payment method.
            </p>

            <form onSubmit={handleRequestReturn} className="space-y-4">
              <div className="space-y-2">
                <label className="text-xs font-semibold text-foreground">
                  Items to Return
                </label>
                <div className="border rounded-md divide-y text-xs">
                  {order.items.map((item) => (
                    <div key={item.id} className="p-3 flex items-center justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <p className="font-semibold text-foreground truncate">{item.product_title}</p>
                        <p className="text-muted-foreground text-[11px]">
                          Max returnable: {item.quantity}
                        </p>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <label className="text-[11px] text-muted-foreground">Qty:</label>
                        <select
                          value={selectedItemQuantities[item.id] || 0}
                          onChange={(e) => {
                            const val = parseInt(e.target.value, 10);
                            setSelectedItemQuantities((prev) => ({
                              ...prev,
                              [item.id]: val,
                            }));
                          }}
                          className="h-8 text-xs p-1 rounded border bg-background text-foreground"
                        >
                          {Array.from({ length: item.quantity + 1 }, (_, i) => (
                            <option key={i} value={i}>
                              {i}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-foreground">
                  Reason for Return
                </label>
                <select
                  value={returnReason}
                  onChange={(e) => setReturnReason(e.target.value)}
                  className="w-full h-9 text-xs p-2 rounded-md border bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500"
                >
                  <option value="">Select a reason...</option>
                  <option value="Defective or damaged item">Defective or damaged item</option>
                  <option value="Incorrect item received">Incorrect item received</option>
                  <option value="Size / fit issue">Size / fit issue</option>
                  <option value="Not as described">Not as described</option>
                  <option value="Quality not satisfactory">Quality not satisfactory</option>
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-foreground">
                  Additional Notes (Optional)
                </label>
                <Input
                  type="text"
                  placeholder="Describe condition or packaging..."
                  value={returnNotes}
                  onChange={(e) => setReturnNotes(e.target.value)}
                  className="h-9 text-xs"
                />
              </div>

              {returnError && <p className="text-xs text-red-600 font-medium">{returnError}</p>}

              <div className="flex justify-end gap-2.5 pt-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setReturnModalOpen(false)}
                  disabled={returnLoading}
                  className="text-xs"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={returnLoading}
                  className="bg-purple-600 hover:bg-purple-700 text-white text-xs"
                >
                  {returnLoading ? "Submitting..." : "Submit Return Request"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
