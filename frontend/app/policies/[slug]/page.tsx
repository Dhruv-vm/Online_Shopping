"use client";

import { use } from "react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { useI18n } from "@/lib/i18n/i18n-context";

const POLICIES = ["returns", "shipping", "privacy", "terms"] as const;

export default function PolicyPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  const { t } = useI18n();
  if (!POLICIES.includes(slug as (typeof POLICIES)[number])) notFound();
  return (
    <div className="container-page max-w-3xl py-12">
      <Link href="/" className="text-sm text-brand underline">{t("common.backToStore")}</Link>
      <h1 className="mt-4 text-3xl font-bold">{t(`policy.${slug}.title`)}</h1>
      <p className="mt-2 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">{t("policy.draftNotice")}</p>
      <div className="prose mt-6 max-w-none space-y-4 text-sm leading-relaxed text-charcoal/90">
        {t(`policy.${slug}.body`)
          .split("\n")
          .map((p, i) => (
            <p key={i}>{p}</p>
          ))}
      </div>
    </div>
  );
}
