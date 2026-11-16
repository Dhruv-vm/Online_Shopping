import { SystemStatus } from "@/components/shared/system-status";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Layers, Database, Radio, Search, ShieldCheck } from "lucide-react";

export default function HomePage() {
  return (
    <div className="container mx-auto space-y-10 px-4 py-10 sm:px-6">
      {/* Hero Section */}
      <section className="space-y-4">
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="border-emerald-600/30 text-emerald-700 dark:text-emerald-400">
            Phase 0 Complete
          </Badge>
          <span className="text-xs text-muted-foreground">Monorepo Baseline Ready</span>
        </div>
        <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl md:text-5xl">
          BASKET Engineering Foundation
        </h1>
        <p className="max-w-3xl text-base text-muted-foreground sm:text-lg">
          A high-reliability, multi-category retail platform for an Indian retail chain.
          Designed for a two-developer team with strict contracts, transactional integrity, and event-driven architecture.
        </p>
      </section>

      {/* Live System Status */}
      <section id="status">
        <SystemStatus />
      </section>

      {/* Architectural Responsibilities */}
      <section id="architecture" className="space-y-4">
        <div className="space-y-1">
          <h2 className="text-2xl font-bold tracking-tight">Core Infrastructure Responsibilities</h2>
          <p className="text-sm text-muted-foreground">
            Strict boundaries enforced per <code className="font-mono text-xs">ARCHITECTURE.md</code>
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center space-x-2">
                <Database className="h-5 w-5 text-blue-600" />
                <CardTitle className="text-base">Aiven PostgreSQL</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-2 text-xs text-muted-foreground">
              <p className="font-medium text-foreground">Authoritative System of Record</p>
              <p>
                Sole authority for catalog items, prices, inventory reservations, carts, orders, and payment states.
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center space-x-2">
                <Radio className="h-5 w-5 text-purple-600" />
                <CardTitle className="text-base">Aiven Apache Kafka</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-2 text-xs text-muted-foreground">
              <p className="font-medium text-foreground">Domain Event Transport</p>
              <p>
                Reliable asynchronous domain events fed by the Transactional Outbox pattern with idempotent consumer execution.
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center space-x-2">
                <Search className="h-5 w-5 text-amber-600" />
                <CardTitle className="text-base">Aiven OpenSearch</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-2 text-xs text-muted-foreground">
              <p className="font-medium text-foreground">Derived Search Index</p>
              <p>
                High-speed search discovery and faceting. Never used for checkout validation or authoritative stock checks.
              </p>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Two Developer Roles */}
      <section id="stack" className="space-y-4">
        <h2 className="text-2xl font-bold tracking-tight">Two-Developer Implementation Scope</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <Card>
            <CardHeader>
              <div className="flex items-center space-x-2">
                <Layers className="h-5 w-5 text-emerald-600" />
                <CardTitle className="text-base">Developer 1 — Backend & Data</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-2 text-xs text-muted-foreground">
              <ul className="list-disc space-y-1 pl-4">
                <li>FastAPI Modular Monolith & SQLAlchemy 2.x</li>
                <li>PostgreSQL schemas and single-head Alembic migrations</li>
                <li>Transactional Outbox & Kafka publishers/workers</li>
                <li>Server-side inventory reservation & checkout state machine</li>
              </ul>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center space-x-2">
                <ShieldCheck className="h-5 w-5 text-emerald-600" />
                <CardTitle className="text-base">Developer 2 — Storefront & Experience</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-2 text-xs text-muted-foreground">
              <ul className="list-disc space-y-1 pl-4">
                <li>Next.js 15 App Router & React 19</li>
                <li>Strict TypeScript with strongly-typed API client</li>
                <li>Storefront catalog, responsive navigation, and cart/checkout UI</li>
                <li>Zero-dead-buttons policy and graceful error boundaries</li>
              </ul>
            </CardContent>
          </Card>
        </div>
      </section>
    </div>
  );
}
