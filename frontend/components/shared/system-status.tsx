"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, AlertCircle, RefreshCw, Server, Database } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { apiClient } from "@/lib/api/client";
import type { HealthResponse, ReadyResponse } from "@/types";

export function SystemStatus() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [ready, setReady] = useState<ReadyResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = async () => {
    setLoading(true);
    setError(null);
    try {
      const [h, r] = await Promise.all([
        apiClient.getHealth().catch((e) => {
          throw new Error(`Backend unavailable: ${e.message}`);
        }),
        apiClient.getReady().catch(() => null),
      ]);
      setHealth(h);
      setReady(r);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to connect to backend.";
      setError(msg);
      setHealth(null);
      setReady(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  return (
    <Card className="w-full">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
        <div>
          <CardTitle className="text-lg">Backend System Connectivity</CardTitle>
          <CardDescription>
            Live verification of API liveness and database readiness endpoints
          </CardDescription>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={fetchStatus}
          disabled={loading}
          className="h-8 gap-1.5"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading && !health && !error && (
          <div className="flex items-center justify-center py-6 text-sm text-muted-foreground">
            <RefreshCw className="mr-2 h-4 w-4 animate-spin text-emerald-600" />
            Connecting to backend at {process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}...
          </div>
        )}

        {error && (
          <div className="rounded-lg border border-amber-500/20 bg-amber-500/10 p-4 text-sm text-amber-800 dark:text-amber-300">
            <div className="flex items-start gap-2.5">
              <AlertCircle className="h-5 w-5 flex-shrink-0 text-amber-600" />
              <div>
                <p className="font-semibold">Backend Unreachable</p>
                <p className="mt-0.5 text-xs text-amber-700 dark:text-amber-400">{error}</p>
                <p className="mt-2 text-xs">
                  Run <code className="rounded bg-black/10 px-1 py-0.5 font-mono">cd backend && uvicorn app.main:app --reload --port 8000</code> to start the backend.
                </p>
              </div>
            </div>
          </div>
        )}

        {health && (
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="flex items-center justify-between rounded-lg border p-3">
              <div className="flex items-center space-x-3">
                <Server className="h-5 w-5 text-emerald-600" />
                <div>
                  <p className="text-xs font-medium text-muted-foreground">FastAPI Process</p>
                  <p className="text-sm font-semibold">{health.service}</p>
                </div>
              </div>
              <Badge variant="success" className="gap-1">
                <CheckCircle2 className="h-3 w-3" />
                {health.status.toUpperCase()}
              </Badge>
            </div>

            <div className="flex items-center justify-between rounded-lg border p-3">
              <div className="flex items-center space-x-3">
                <Database className="h-5 w-5 text-blue-600" />
                <div>
                  <p className="text-xs font-medium text-muted-foreground">Database Readiness</p>
                  <p className="text-sm font-semibold">
                    {ready?.checks?.database?.status === "connected"
                      ? "Aiven PostgreSQL"
                      : "Unconfigured (Local)"}
                  </p>
                </div>
              </div>
              {ready?.checks?.database?.status === "connected" ? (
                <Badge variant="success" className="gap-1">
                  <CheckCircle2 className="h-3 w-3" />
                  CONNECTED
                </Badge>
              ) : (
                <Badge variant="warning" className="gap-1">
                  <AlertCircle className="h-3 w-3" />
                  UNCONFIGURED
                </Badge>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
