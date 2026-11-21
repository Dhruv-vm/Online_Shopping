"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { ArrowRight } from "lucide-react";
import { ProductImage } from "@/components/catalogue/product-image";
import { Reveal } from "@/components/motion/reveal";

export type BannerImage = { src?: string | null; alt: string };
export type BannerTone = "green" | "ink" | "yellow";

const TONES: Record<BannerTone, { bg: string; text: string; eyebrow: string; body: string; cta: string; band: string; band2: string }> = {
  green: { bg: "bg-forest", text: "text-white", eyebrow: "text-brand-yellow", body: "text-white/80", cta: "bg-brand-yellow text-ink group-hover:bg-white", band: "#FDCD1E", band2: "#145A3A" },
  ink: { bg: "bg-ink", text: "text-white", eyebrow: "text-brand-yellow", body: "text-white/75", cta: "bg-brand-yellow text-ink group-hover:bg-white", band: "#FDCD1E", band2: "#1F1F1F" },
  yellow: { bg: "bg-brand-yellow", text: "text-ink", eyebrow: "text-forest", body: "text-ink/75", cta: "bg-ink text-white group-hover:bg-forest", band: "#0E3B27", band2: "#F5C000" },
};

/**
 * Reusable campaign / advertisement banner: deals, category promotions, seasonal
 * campaigns and collections. "wide" is the full-width hero ad with diagonal brand
 * bands and product photography; "compact" is a half-width campaign tile.
 * Presentation only — callers pass real copy, links and images.
 */
export function CampaignBanner({
  eyebrow,
  title,
  body,
  cta,
  href,
  images = [],
  tone = "green",
  size = "wide",
  badge,
  ariaLabel,
}: {
  eyebrow: string;
  title: ReactNode;
  body?: string;
  cta: string;
  href: string;
  images?: BannerImage[];
  tone?: BannerTone;
  size?: "wide" | "compact";
  /** Small decorative tag shown over the artwork (e.g. "%"). */
  badge?: ReactNode;
  ariaLabel?: string;
}) {
  const c = TONES[tone];
  const wide = size === "wide";
  const [first, second] = images.filter((i) => i.src);
  return (
    <Link
      href={href}
      aria-label={ariaLabel}
      className={`group relative isolate block overflow-hidden ${wide ? "rounded-hero" : "rounded-card"} ${c.bg} ${c.text} shadow-card transition-shadow duration-base ease-out hover:shadow-card-hover`}
    >
      {/* Diagonal brand bands */}
      <svg aria-hidden className="absolute inset-0 -z-10 h-full w-full" viewBox="0 0 1000 300" preserveAspectRatio="none">
        {wide ? (
          <>
            <path d="M470 300 C 560 250, 540 130, 640 60 C 690 25, 720 10, 760 0 L1000 0 L1000 300 Z" fill={c.band2} />
            <path d="M540 300 C 630 250, 610 140, 700 70 C 745 35, 780 14, 830 0 L1000 0 L1000 300 Z" fill={c.band} />
          </>
        ) : (
          <>
            <path d="M720 0 L1000 0 L1000 300 L590 300 C 680 210, 715 110, 720 0 Z" fill={c.band2} />
            <path d="M800 0 L1000 0 L1000 300 L680 300 C 760 210, 795 110, 800 0 Z" fill={c.band} />
          </>
        )}
      </svg>

      <div className={`relative grid items-center ${wide ? "min-h-[15rem] gap-6 p-7 sm:min-h-[16.5rem] sm:grid-cols-[1.1fr_1fr] sm:p-10 lg:px-12" : "min-h-[12rem] grid-cols-[1.25fr_1fr] gap-3 p-6 sm:p-7"}`}>
        <div className="max-w-lg">
          <p className={`text-[11px] font-bold uppercase tracking-[0.22em] sm:text-xs ${c.eyebrow}`}>{eyebrow}</p>
          <p className={`mt-2 font-extrabold leading-[1.02] tracking-[-0.025em] ${wide ? "text-[2.5rem] sm:text-[3.5rem] lg:text-[3.9rem]" : "text-2xl sm:text-[1.75rem]"}`}>{title}</p>
          {body && <p className={`mt-3 max-w-sm text-sm ${wide ? "sm:text-base" : ""} ${c.body}`}>{body}</p>}
          <span className={`press mt-5 inline-flex items-center gap-2 rounded-full font-bold transition-colors duration-base ${wide ? "h-11 pl-6 pr-5 text-sm sm:mt-6" : "h-10 pl-5 pr-4 text-[13px]"} ${c.cta}`}>
            {cta}
            <ArrowRight className="h-4 w-4 transition-transform duration-base ease-out group-hover:translate-x-1" />
          </span>
        </div>

        <div className={`relative h-full ${wide ? "hidden min-h-[12rem] sm:block" : "min-h-[9rem]"}`}>
          {first && (
            <span
              className={`absolute block overflow-hidden bg-white shadow-card-hover ring-[5px] ring-white transition-transform duration-slow ease-out ${
                wide
                  ? "left-[6%] top-1/2 h-[82%] w-[44%] -translate-y-1/2 -rotate-[4deg] rounded-[1.6rem] group-hover:-rotate-2 group-hover:scale-[1.03]"
                  : "right-[6%] top-1/2 h-[86%] w-[78%] -translate-y-1/2 rotate-3 rounded-2xl group-hover:rotate-1 group-hover:scale-[1.03]"
              }`}
            >
              <ProductImage src={first.src} alt={first.alt} sizes={wide ? "22vw" : "30vw"} />
            </span>
          )}
          {wide && second && (
            <span className="absolute right-[4%] top-[56%] block h-[62%] w-[38%] -translate-y-1/2 rotate-[5deg] overflow-hidden rounded-[1.4rem] bg-white shadow-card-hover ring-[5px] ring-white transition-transform duration-slow ease-out group-hover:rotate-3 group-hover:scale-[1.03]">
              <ProductImage src={second.src} alt={second.alt} sizes="18vw" />
            </span>
          )}
          {badge && wide && (
            <span aria-hidden className="absolute left-[44%] top-[2%] flex flex-col items-center">
              <span className="h-5 w-px bg-white/50" />
              <span className="flex h-16 w-14 items-center justify-center rounded-xl bg-brand-yellow text-3xl font-black text-ink shadow-card-hover [transform:rotate(-8deg)] transition-transform duration-slow ease-out group-hover:[transform:rotate(-2deg)]">
                {badge}
              </span>
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}

/** Section wrapper that reveals a banner on scroll with the page gutter. */
export function BannerSection({ children, className = "pt-12" }: { children: ReactNode; className?: string }) {
  return (
    <Reveal as="section" className={`container-page ${className}`}>
      {children}
    </Reveal>
  );
}
