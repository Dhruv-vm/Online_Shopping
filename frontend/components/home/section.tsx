import Link from "next/link";
import type { ReactNode } from "react";
import { ArrowRight } from "lucide-react";

export function Section({
  id,
  title,
  subtitle,
  href,
  linkLabel,
  children,
  tone = "plain",
}: {
  id?: string;
  title: string;
  subtitle?: string;
  href?: string;
  linkLabel?: string;
  children: ReactNode;
  tone?: "plain" | "tint" | "dark";
}) {
  const bg = tone === "tint" ? "bg-brand-light/50" : tone === "dark" ? "bg-brand-dark text-white" : "";
  return (
    <section id={id} className={`py-10 sm:py-12 ${bg}`} aria-labelledby={id ? `${id}-title` : undefined}>
      <div className="container-page">
        <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 id={id ? `${id}-title` : undefined} className={`text-2xl font-bold tracking-tight ${tone === "dark" ? "text-white" : "text-charcoal"}`}>
              {title}
            </h2>
            {subtitle && <p className={`mt-1 max-w-2xl text-sm ${tone === "dark" ? "text-white/75" : "text-muted-foreground"}`}>{subtitle}</p>}
          </div>
          {href && linkLabel && (
            <Link href={href} className={`inline-flex items-center gap-1 text-sm font-semibold ${tone === "dark" ? "text-brand-yellow" : "text-brand-dark"} hover:underline`}>
              {linkLabel} <ArrowRight className="h-4 w-4" />
            </Link>
          )}
        </div>
        {children}
      </div>
    </section>
  );
}

export function Rail({ children }: { children: ReactNode }) {
  return <div className="no-scrollbar -mx-4 flex snap-x gap-4 overflow-x-auto px-4 pb-2 sm:mx-0 sm:grid sm:grid-cols-3 sm:overflow-visible sm:px-0 lg:grid-cols-4 xl:grid-cols-5 [&>*]:w-56 [&>*]:shrink-0 [&>*]:snap-start sm:[&>*]:w-auto">{children}</div>;
}

export function SkeletonCards({ n = 5 }: { n?: number }) {
  return (
    <Rail>
      {Array.from({ length: n }).map((_, i) => (
        <div key={i} className="h-72 animate-pulse rounded-xl border bg-white" />
      ))}
    </Rail>
  );
}
