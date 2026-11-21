"use client";

import { useEffect, useState, useCallback } from "react";
import {
  ShoppingCart,
  Search,
  Package,
  Clock,
  CheckCircle2,
  Truck,
  XCircle,
  AlertCircle,
  RefreshCw,
  MapPin,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiClient } from "@/lib/api/client";
import type { RetailerOrderListItem } from "@/types";
import { useLiveUpdates } from "@/lib/realtime";

const STATUS_TABS = [
  { id: "ALL", label: "All Orders" },
  { id: "CONFIRMED", label: "Confirmed" },
  { id: "PROCESSING", label: "Processing" },
  { id: "PACKED", label: "Packed" },
  { id: "SHIPPED", label: "Shipped" },
  { id: "DELIVERED", label: "Delivered" },
  { id: "CANCELLED", label: "Cancelled" },
];

export default function RetailerOrdersPage() {
  const [orders, setOrders] = useState<RetailerOrderListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [updatingOrderId, setUpdatingOrderId] = useState<string | null>(null);
  const [expandedOrderId, setExpandedOrderId] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const loadOrders = useCallback(async (opts?: { quiet?: boolean }) => {
    if (!opts?.quiet) setIsLoading(true);
    setErrorMsg(null);
    try {
      const res = await apiClient.listRetailerOrders({
        status: statusFilter === "ALL" ? undefined : statusFilter,
        search: searchQuery.trim() || undefined,
        limit: 50,
      });
      setOrders(res.items);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to load store orders.");
    } finally {
      setIsLoading(false);
    }
  }, [statusFilter, searchQuery]);

  useEffect(() => {
    loadOrders();
  }, [loadOrders]);
  useLiveUpdates(["order.", "payment.", "fulfilment."], () => void loadOrders({ quiet: true }));

  const handleUpdateStatus = async (orderId: string, nextStatus: string) => {
    setUpdatingOrderId(orderId);
    try {
      await apiClient.updateRetailerOrderStatus(orderId, { status: nextStatus });
      await loadOrders();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to update order status.");
    } finally {
      setUpdatingOrderId(null);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "CONFIRMED":
        return <Badge className="bg-blue-600 text-white border-0">Confirmed</Badge>;
      case "PROCESSING":
        return <Badge className="bg-amber-600 text-white border-0">Processing</Badge>;
      case "PACKED":
        return <Badge className="bg-purple-600 text-white border-0">Packed</Badge>;
      case "SHIPPED":
        return <Badge className="bg-indigo-600 text-white border-0">Shipped</Badge>;
      case "DELIVERED":
        return <Badge className="bg-emerald-600 text-white border-0">Delivered</Badge>;
      case "CANCELLED":
        return <Badge variant="destructive">Cancelled</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <ShoppingCart className="h-6 w-6 text-blue-600" />
            Store Orders & Fulfilment
          </h1>
          <p className="text-sm text-muted-foreground">
            Manage incoming orders, update dispatch and shipment stages, and view customer delivery details.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => void loadOrders()}
          disabled={isLoading}
          className="gap-2 shrink-0"
        >
          <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {/* Filter Tabs & Search */}
      <div className="space-y-4">
        <div className="flex flex-wrap gap-2 border-b pb-3">
          {STATUS_TABS.map((tab) => (
            <Button
              key={tab.id}
              variant={statusFilter === tab.id ? "default" : "outline"}
              size="sm"
              onClick={() => setStatusFilter(tab.id)}
              className={statusFilter === tab.id ? "bg-blue-600 hover:bg-blue-700 text-white" : ""}
            >
              {tab.label}
            </Button>
          ))}
        </div>

        <div className="relative max-w-md">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search by order number (e.g. ORD-DEMO-)..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9 text-sm"
          />
        </div>
      </div>

      {errorMsg && (
        <div className="p-4 rounded-xl border border-red-500/30 bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 text-sm flex items-center gap-3">
          <AlertCircle className="h-5 w-5 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Orders List */}
      {isLoading ? (
        <div className="p-12 text-center text-muted-foreground space-y-3 border rounded-xl bg-card">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-blue-600 border-r-transparent align-[-0.125em]" />
          <p className="text-sm">Retrieving store orders from database...</p>
        </div>
      ) : orders.length === 0 ? (
        <div className="p-12 text-center text-muted-foreground space-y-3 border border-dashed rounded-xl bg-card">
          <Package className="h-10 w-10 mx-auto text-muted-foreground/60" />
          <h3 className="font-semibold text-foreground text-base">No Orders Found</h3>
          <p className="text-sm max-w-sm mx-auto">
            No orders match the selected status filter. Orders containing products from your store will appear here automatically.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {orders.map((order) => {
            const isExpanded = expandedOrderId === order.id;
            return (
              <div
                key={order.id}
                className="rounded-xl border bg-card p-5 shadow-xs transition-all hover:border-blue-500/40"
              >
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-4 border-b">
                  <div className="space-y-1">
                    <div className="flex items-center gap-3">
                      <span className="font-mono font-bold text-foreground text-base">
                        {order.order_number}
                      </span>
                      {getStatusBadge(order.status)}
                      <Badge variant="outline" className="text-xs">
                        Payment: {order.payment_status}
                      </Badge>
                    </div>
                    <div className="text-xs text-muted-foreground flex flex-wrap items-center gap-3">
                      <span>Customer: <strong className="text-foreground">{order.customer_name}</strong></span>
                      {order.delivery_city && (
                        <span className="flex items-center gap-1">
                          <MapPin className="h-3 w-3" /> {order.delivery_city}, {order.delivery_state}
                        </span>
                      )}
                      <span>Placed: {new Date(order.created_at).toLocaleString()}</span>
                    </div>
                  </div>

                  {/* Pricing summary */}
                  <div className="flex items-center gap-6">
                    <div className="text-right">
                      <div className="text-xs text-muted-foreground">Store Order Value</div>
                      <div className="text-lg font-bold text-foreground font-mono">
                        ₹{(order.retailer_total_paise / 100).toFixed(2)}
                      </div>
                      <div className="text-[10px] text-muted-foreground">
                        {order.total_items} item(s) • Tax: ₹{(order.retailer_tax_paise / 100).toFixed(2)}
                      </div>
                    </div>

                    {/* Status Action Buttons */}
                    <div className="flex items-center gap-2">
                      {order.status === "CONFIRMED" && (
                        <Button
                          size="sm"
                          className="bg-amber-600 hover:bg-amber-700 text-white text-xs gap-1"
                          disabled={updatingOrderId === order.id}
                          onClick={() => handleUpdateStatus(order.id, "PROCESSING")}
                        >
                          <Clock className="h-3.5 w-3.5" />
                          Process Order
                        </Button>
                      )}
                      {order.status === "PROCESSING" && (
                        <Button
                          size="sm"
                          className="bg-purple-600 hover:bg-purple-700 text-white text-xs gap-1"
                          disabled={updatingOrderId === order.id}
                          onClick={() => handleUpdateStatus(order.id, "PACKED")}
                        >
                          <Package className="h-3.5 w-3.5" />
                          Mark Packed
                        </Button>
                      )}
                      {order.status === "PACKED" && (
                        <Button
                          size="sm"
                          className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs gap-1"
                          disabled={updatingOrderId === order.id}
                          onClick={() => handleUpdateStatus(order.id, "SHIPPED")}
                        >
                          <Truck className="h-3.5 w-3.5" />
                          Ship Order
                        </Button>
                      )}
                      {order.status === "SHIPPED" && (
                        <Button
                          size="sm"
                          className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs gap-1"
                          disabled={updatingOrderId === order.id}
                          onClick={() => handleUpdateStatus(order.id, "DELIVERED")}
                        >
                          <CheckCircle2 className="h-3.5 w-3.5" />
                          Mark Delivered
                        </Button>
                      )}
                      {order.status !== "DELIVERED" && order.status !== "CANCELLED" && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="text-red-600 hover:text-red-700 hover:bg-red-50 text-xs"
                          disabled={updatingOrderId === order.id}
                          onClick={() => {
                            if (confirm(`Cancel order ${order.order_number}?`)) {
                              handleUpdateStatus(order.id, "CANCELLED");
                            }
                          }}
                        >
                          <XCircle className="h-3.5 w-3.5" />
                        </Button>
                      )}

                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setExpandedOrderId(isExpanded ? null : order.id)}
                        className="text-xs"
                      >
                        {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                      </Button>
                    </div>
                  </div>
                </div>

                {/* Items in this order */}
                <div className="pt-3">
                  <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                    Store Items ({order.items.length})
                  </div>
                  <div className="divide-y divide-border/60">
                    {order.items.map((item) => (
                      <div key={item.id} className="py-2 flex items-center justify-between text-xs">
                        <div className="space-y-0.5">
                          <span className="font-semibold text-foreground">{item.product_title}</span>
                          <div className="text-[11px] text-muted-foreground">
                            Variant: {item.variant_title} • SKU: <span className="font-mono">{item.sku || "N/A"}</span>
                          </div>
                        </div>
                        <div className="text-right font-mono">
                          <div>
                            {item.quantity} × ₹{(item.unit_selling_price_paise / 100).toFixed(2)}
                          </div>
                          <div className="text-muted-foreground font-semibold">
                            = ₹{(item.total_selling_price_paise / 100).toFixed(2)}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Expanded Details */}
                {isExpanded && (
                  <div className="mt-4 pt-4 border-t bg-muted/30 rounded-lg p-3 text-xs space-y-2">
                    <div className="font-bold text-foreground">Delivery & Settlement Breakdown</div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div>
                        <span className="text-muted-foreground block">Customer Name:</span>
                        <span className="font-medium">{order.customer_name}</span>
                        {order.delivery_city && (
                          <>
                            <span className="text-muted-foreground block mt-1">Destination:</span>
                            <span className="font-medium">{order.delivery_city}, {order.delivery_state}</span>
                          </>
                        )}
                      </div>
                      <div className="space-y-1 text-right sm:text-right font-mono">
                        <div>Items Subtotal: ₹{(order.retailer_subtotal_paise / 100).toFixed(2)}</div>
                        <div>Estimated Tax (GST): ₹{(order.retailer_tax_paise / 100).toFixed(2)}</div>
                        <div className="font-bold text-foreground text-sm border-t pt-1">
                          Net Store Total: ₹{(order.retailer_total_paise / 100).toFixed(2)}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
