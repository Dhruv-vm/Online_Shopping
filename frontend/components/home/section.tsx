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
  const bg = tone === "tint" ? "bg-cream/60" : tone === "dark" ? "bg-ink text-white" : "";
  return (
    <section id={id} className={`py-10 sm:py-12 ${bg}`} aria-labelledby={id ? `${id}-title` : undefined}>
      <div className="container-page">
        <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 id={id ? `${id}-title` : undefined} className={`text-[1.6rem] font-extrabold tracking-[-0.02em] sm:text-[1.85rem] ${tone === "dark" ? "text-white" : "text-ink"}`}>
              {title}
            </h2>
            {subtitle && <p className={`mt-1 max-w-2xl text-sm ${tone === "dark" ? "text-white/75" : "text-muted-foreground"}`}>{subtitle}</p>}
          </div>
          {href && linkLabel && (
            <Link href={href} className={`group inline-flex items-center gap-1.5 border-b-2 pb-0.5 text-sm font-bold transition-colors duration-base ${tone === "dark" ? "border-brand-yellow/30 text-brand-yellow hover:border-brand-yellow" : "border-brand-green-logo/25 text-brand-green-logo hover:border-brand-green-logo"}`}>
              {linkLabel} <ArrowRight className="h-4 w-4 transition-transform duration-base ease-out group-hover:translate-x-1" />
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
        <div key={i} className="h-72 animate-pulse rounded-card bg-white shadow-card" />
      ))}
    </Rail>
  );
}
