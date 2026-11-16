export function Footer() {
  return (
    <footer className="w-full border-t bg-muted/30 py-8 text-center text-xs text-muted-foreground">
      <div className="container mx-auto px-4">
        <p className="font-medium text-foreground/80">
          BASKET — Multi-Category Retail Platform for India
        </p>
        <p className="mt-1">
          Engineering Foundation Phase 0 • Built with Next.js 15, FastAPI, Aiven PostgreSQL, Kafka & OpenSearch.
        </p>
      </div>
    </footer>
  );
}
