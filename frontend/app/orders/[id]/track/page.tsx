"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  Truck,
  ArrowLeft,
  CheckCircle2,
  Clock,
  ExternalLink,
  Package,
  MapPin,
  Calendar,
  AlertCircle,
  Loader2,
  ShieldCheck,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiClient } from "@/lib/api/client";
import type { OrderTrackingResponse } from "@/types/index";

export default function OrderTrackingPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const searchParams = useSearchParams();
  const resolvedParams = use(params);
  const orderId = resolvedParams.id;
  const accessToken = searchParams.get("access_token") || undefined;

  const [tracking, setTracking] = useState<OrderTrackingResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchTracking = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await apiClient.getOrderTracking(orderId, accessToken);
        setTracking(data);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Failed to load tracking.";
        setError(msg);
      } finally {
        setLoading(false);
      }
    };

    fetchTracking();
  }, [orderId, accessToken]);

  const querySuffix = accessToken ? `?access_token=${encodeURIComponent(accessToken)}` : "";

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-16 flex flex-col items-center justify-center text-muted-foreground">
        <Loader2 className="h-8 w-8 animate-spin text-emerald-600 mb-3" />
        <p className="text-sm font-medium">Fetching live tracking status...</p>
      </div>
    );
  }

  if (error || !tracking) {
    return (
      <div className="container mx-auto px-4 py-12 max-w-2xl text-center">
        <div className="p-8 rounded-xl border border-red-200 bg-red-50/50 dark:bg-red-950/20 text-red-700 dark:text-red-300 space-y-4">
          <AlertCircle className="h-10 w-10 text-red-600 mx-auto" />
          <h2 className="text-lg font-bold">Tracking Unavailable</h2>
          <p className="text-xs">{error || "Unable to retrieve tracking details."}</p>
          <div className="pt-2">
            <Link href={`/orders/${orderId}${querySuffix}`}>
              <Button size="sm" variant="outline" className="text-xs">
                Back to Order Details
              </Button>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl">
      {/* Back button */}
      <div className="flex items-center gap-2 mb-6">
        <Link
          href={`/orders/${orderId}${querySuffix}`}
          className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to Order Details
        </Link>
      </div>

      {/* Header Banner */}
      <div className="bg-card border rounded-xl p-6 mb-6 shadow-xs flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2.5">
            <Truck className="h-5 w-5 text-emerald-600" />
            <h1 className="text-xl font-bold font-mono text-foreground">
              {tracking.order_number}
            </h1>
          </div>
          <p className="text-xs text-muted-foreground">
            Current Status: <span className="font-semibold text-foreground">{tracking.order_status}</span>
          </p>
        </div>

        {tracking.tracking_url && (
          <a
            href={tracking.tracking_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center justify-center gap-1.5 h-9 px-4 rounded-md bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-medium shadow-xs"
          >
            Track on Carrier Site
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        )}
      </div>

      {/* Visual Stepper Timeline */}
      <Card className="mb-6">
        <CardHeader className="py-4 px-5 border-b">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <Clock className="h-4 w-4 text-emerald-600" />
            Order Progress Stepper
          </CardTitle>
        </CardHeader>
        <CardContent className="p-6">
          <div className="relative flex flex-col md:flex-row justify-between gap-4 md:gap-0">
            {tracking.timeline.map((step, idx) => {
              const isFirst = idx === 0;
              const isLast = idx === tracking.timeline.length - 1;

              return (
                <div key={step.status} className="flex-1 flex md:flex-col items-start md:items-center relative">
                  {/* Connector Line (Desktop) */}
                  {!isLast && (
                    <div
                      className={`hidden md:block absolute top-4 left-1/2 w-full h-0.5 z-0 ${
                        step.completed ? "bg-emerald-600" : "bg-muted"
                      }`}
                    />
                  )}

                  {/* Icon Step Circle */}
                  <div
                    className={`relative z-10 flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold transition-colors ${
                      step.completed
                        ? "bg-emerald-600 text-white shadow-xs"
                        : step.current
                        ? "bg-emerald-100 text-emerald-700 border-2 border-emerald-600 dark:bg-emerald-950 dark:text-emerald-300 ring-4 ring-emerald-500/20"
                        : "bg-muted text-muted-foreground border"
                    }`}
                  >
                    {step.completed ? (
                      <CheckCircle2 className="h-4 w-4" />
                    ) : (
                      idx + 1
                    )}
                  </div>

                  {/* Step Label */}
                  <div className="ml-3 md:ml-0 md:mt-2.5 md:text-center">
                    <p
                      className={`text-xs font-semibold ${
                        step.current
                          ? "text-emerald-600 dark:text-emerald-400"
                          : step.completed
                          ? "text-foreground"
                          : "text-muted-foreground"
                      }`}
                    >
                      {step.title}
                    </p>
                    <p className="text-[10px] text-muted-foreground hidden md:block max-w-[110px] mx-auto mt-0.5">
                      {step.description}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Carrier & Shipment Details */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        {/* Carrier Info Card */}
        <Card>
          <CardHeader className="py-4 px-5 border-b">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-emerald-600" />
              Logistics & Carrier Details
            </CardTitle>
          </CardHeader>
          <CardContent className="p-5 text-xs space-y-2.5 text-muted-foreground">
            <div>
              <span className="text-[11px] block">Carrier Name:</span>
              <span className="font-semibold text-foreground text-sm">
                {tracking.carrier_name || "Internal BASKET Fulfillment"}
              </span>
            </div>

            {tracking.tracking_number && (
              <div>
                <span className="text-[11px] block">Tracking / AWB Number:</span>
                <span className="font-mono font-medium text-foreground text-xs select-all">
                  {tracking.tracking_number}
                </span>
              </div>
            )}

            {tracking.estimated_delivery_at && (
              <div>
                <span className="text-[11px] block">Estimated Delivery Date:</span>
                <span className="font-medium text-foreground">
                  {new Date(tracking.estimated_delivery_at).toLocaleDateString("en-IN", {
                    weekday: "short",
                    month: "long",
                    day: "numeric",
                    year: "numeric",
                  })}
                </span>
              </div>
            )}

            {tracking.delivered_at && (
              <div>
                <span className="text-[11px] block text-emerald-600 font-semibold">Delivered On:</span>
                <span className="font-medium text-foreground">
                  {new Date(tracking.delivered_at).toLocaleDateString("en-IN", {
                    month: "long",
                    day: "numeric",
                    year: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Packages / Shipments Count */}
        <Card>
          <CardHeader className="py-4 px-5 border-b">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Package className="h-4 w-4 text-emerald-600" />
              Shipment Consignments ({tracking.shipments.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="p-5 text-xs space-y-3">
            {tracking.shipments.length === 0 ? (
              <p className="text-muted-foreground italic">
                Your order is currently being prepared for shipment. Tracking details will update once dispatched.
              </p>
            ) : (
              tracking.shipments.map((s) => (
                <div key={s.id} className="p-3 rounded-lg border bg-muted/20 space-y-1">
                  <div className="flex justify-between items-center font-mono font-medium text-foreground">
                    <span>{s.shipment_number}</span>
                    <Badge variant="outline" className="text-[10px]">
                      {s.status}
                    </Badge>
                  </div>
                  <p className="text-muted-foreground text-[11px]">
                    Carrier: {s.carrier_name} • AWB: {s.tracking_number}
                  </p>
                  <p className="text-muted-foreground text-[11px]">
                    Items in consignment: {s.items.reduce((sum, item) => sum + item.quantity, 0)} units
                  </p>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      {/* Carrier Event History Log */}
      {tracking.shipments.some((s) => s.carrier_event_history && s.carrier_event_history.length > 0) && (
        <Card>
          <CardHeader className="py-4 px-5 border-b">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <MapPin className="h-4 w-4 text-emerald-600" />
              Live Carrier Event Updates
            </CardTitle>
          </CardHeader>
          <CardContent className="p-5">
            <div className="relative pl-6 space-y-4 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-muted-foreground/20">
              {tracking.shipments.flatMap((s) =>
                (s.carrier_event_history || []).map((evt, idx) => (
                  <div key={idx} className="relative text-xs space-y-0.5">
                    <div className="absolute -left-6 top-1 h-2.5 w-2.5 rounded-full bg-emerald-600 ring-4 ring-background" />
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-semibold text-foreground">{evt.status}</span>
                      {evt.location && (
                        <span className="text-muted-foreground">• {evt.location}</span>
                      )}
                      <span className="text-[10px] text-muted-foreground ml-auto">
                        {new Date(evt.timestamp).toLocaleDateString("en-IN", {
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                    </div>
                    <p className="text-muted-foreground text-[11px]">{evt.description}</p>
                  </div>
                )),
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
