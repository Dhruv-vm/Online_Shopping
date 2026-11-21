"use client";

import { useEffect, useMemo, useState } from "react";
import { Reveal } from "@/components/motion/reveal";
import { useI18n } from "@/lib/i18n/i18n-context";
import { encodeQr, qrPath } from "@/lib/qr";

function AppleGlyph() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden className="h-6 w-6 fill-current">
      <path d="M16.37 12.73c-.02-2.2 1.8-3.26 1.88-3.31-1.03-1.5-2.62-1.7-3.18-1.73-1.35-.14-2.64.8-3.33.8-.69 0-1.74-.78-2.87-.76-1.47.02-2.83.86-3.59 2.18-1.53 2.66-.39 6.6 1.1 8.75.73 1.05 1.6 2.24 2.73 2.2 1.1-.04 1.51-.71 2.84-.71 1.32 0 1.7.71 2.86.69 1.18-.02 1.93-1.07 2.65-2.13.84-1.22 1.18-2.4 1.2-2.46-.03-.01-2.3-.88-2.32-3.5zM14.2 6.27c.6-.73 1.01-1.75.9-2.77-.87.04-1.92.58-2.54 1.31-.56.64-1.05 1.68-.92 2.68.97.08 1.96-.49 2.56-1.22z" />
    </svg>
  );
}

function PlayGlyph() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden className="h-6 w-6">
      <path d="M4.2 2.6 13.6 12l-9.4 9.4c-.3-.2-.5-.6-.5-1V3.6c0-.4.2-.8.5-1z" fill="#00D7FE" />
      <path d="m16.7 8.9-3.1 3.1-9.4-9.4c.3-.2.8-.2 1.2 0z" fill="#00F076" />
      <path d="m16.7 15.1-11.3 6.3c-.4.2-.9.2-1.2 0l9.4-9.4z" fill="#FF3A44" />
      <path d="M20.2 10.9c.8.5.8 1.7 0 2.2l-3.5 2-3.1-3.1 3.1-3.1z" fill="#FFD400" />
    </svg>
  );
}

function StoreBadge({ glyph, line1, line2 }: { glyph: React.ReactNode; line1: string; line2: string }) {
  return (
    <span className="inline-flex h-[52px] items-center gap-2.5 rounded-xl bg-ink px-4 text-white ring-1 ring-white/20" aria-label={`${line1} ${line2}`}>
      {glyph}
      <span className="leading-none">
        <span className="block text-[9.5px] font-medium uppercase tracking-wide text-white/70">{line1}</span>
        <span className="mt-1 block text-[17px] font-bold tracking-tight">{line2}</span>
      </span>
    </span>
  );
}

/** Real, scannable QR for this site's address (opens Basket on a phone). */
function SiteQr({ alt }: { alt: string }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => setUrl(window.location.origin + "/"), []);
  const m = useMemo(() => {
    if (!url) return null;
    try {
      return encodeQr(url);
    } catch {
      return null;
    }
  }, [url]);
  const size = m?.length ?? 25;
  return (
    <svg viewBox={`-2 -2 ${size + 4} ${size + 4}`} className="h-[88px] w-[88px] shrink-0 rounded-md bg-white sm:h-24 sm:w-24" role="img" aria-label={alt} shapeRendering="crispEdges">
      {m ? <path d={qrPath(m)} fill="#080808" /> : <rect x="0" y="0" width={size} height={size} fill="#F3EFE7" />}
    </svg>
  );
}

/** Phone mockup built in CSS around the official logo (no stock device photo). */
function PhoneMockup() {
  return (
    <div aria-hidden className="relative mx-auto h-[300px] w-[160px] rotate-[-14deg] rounded-[2.2rem] bg-[#1b1b1b] p-[7px] shadow-[0_30px_60px_-20px_rgba(0,0,0,0.6)] ring-1 ring-white/15 sm:h-[340px] sm:w-[178px]">
      <div className="relative h-full w-full overflow-hidden rounded-[1.8rem] bg-gradient-to-b from-[#151515] to-ink">
        <div className="absolute left-1/2 top-2 h-[18px] w-[64px] -translate-x-1/2 rounded-full bg-black" />
        <div className="flex items-center justify-between px-5 pt-[9px] text-[10px] font-semibold text-white">
          <span>9:41</span>
          <span className="flex items-center gap-1">
            <span className="h-2 w-3 rounded-[2px] border border-white/80" />
          </span>
        </div>
        <div className="flex h-[78%] flex-col items-center justify-center">
          {/* eslint-disable-next-line @next/next/no-img-element -- static brand asset */}
          <img src="/brand/basket-logo.webp" alt="" width={120} height={33} className="h-auto w-[120px] select-none" draggable={false} />
          <span className="mt-4 h-1 w-10 rounded-full bg-brand-yellow" />
        </div>
      </div>
    </div>
  );
}

export function AppPromo() {
  const { t } = useI18n();
  return (
    <section aria-labelledby="app-promo-title" className="relative isolate -mb-20 mt-10 overflow-hidden sm:mt-16 bg-forest text-white">
      {/* Curved brand bands */}
      <svg aria-hidden className="absolute inset-0 -z-10 h-full w-full" viewBox="0 0 1440 360" preserveAspectRatio="none">
        <path d="M0 0 H1440 V40 C 1100 10, 700 70, 420 30 C 250 8, 110 20, 0 48 Z" fill="#FAF8F4" />
        <path d="M0 360 V250 C 160 300, 300 330, 520 360 Z" fill="#FDCD1E" />
        <path d="M1440 360 V120 C 1320 220, 1180 300, 960 360 Z" fill="#145A3A" />
        <path d="M1440 360 V230 C 1360 290, 1270 330, 1150 360 Z" fill="#FDCD1E" />
      </svg>
      <div className="container-page relative grid items-center gap-8 pb-12 pt-16 sm:pt-20 md:grid-cols-[minmax(0,15rem)_1fr] md:pb-14 md:pt-24 lg:grid-cols-[minmax(0,18rem)_1fr_auto] lg:gap-12">
        <Reveal className="hidden justify-center md:flex md:-mb-24 md:self-end">
          <PhoneMockup />
        </Reveal>
        <Reveal delay={80}>
          <h2 id="app-promo-title" className="text-[2rem] font-extrabold leading-tight tracking-[-0.02em] sm:text-[2.4rem]">
            {t("home.v2.app.title1")} <span className="text-brand-yellow">{t("home.v2.app.title2")}</span> {t("home.v2.app.title3")}
          </h2>
          <p className="mt-2 max-w-md text-sm text-white/80 sm:text-base">{t("home.v2.app.body")}</p>
          <div className="mt-6 flex flex-wrap gap-3">
            <StoreBadge glyph={<AppleGlyph />} line1={t("home.v2.app.soon")} line2={t("home.v2.app.appStore")} />
            <StoreBadge glyph={<PlayGlyph />} line1={t("home.v2.app.soon")} line2={t("home.v2.app.googlePlay")} />
          </div>
        </Reveal>
        <Reveal delay={160} className="hidden md:col-start-2 md:block lg:col-start-auto">
          <div className="inline-flex items-center gap-4 rounded-2xl bg-white p-3 pr-6 text-ink shadow-card-hover">
            <SiteQr alt={t("home.v2.app.qrAlt")} />
            <p className="text-lg font-extrabold leading-tight">
              {t("home.v2.app.scan1")}
              <br />
              <span className="text-ink/70">{t("home.v2.app.scan2")}</span>
            </p>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
