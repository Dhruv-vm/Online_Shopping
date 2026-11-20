"use client";

import { listCampaigns } from "@/lib/api/phase3";
import { useI18n } from "@/lib/i18n/i18n-context";
import { CampaignCard } from "@/components/phase3/campaign-card";
import { PageTitle, Status, useLoad } from "@/components/phase3/kit";

export default function CommunityBuyingPage() {
  const { t } = useI18n();
  const { data, setData, loading, error, reload } = useLoad(() => listCampaigns({ limit: 50 }));
  return (
    <div className="container mx-auto max-w-5xl px-4 py-8">
      <PageTitle title={t("nav.communityBuying")} subtitle="Join neighbours to unlock bulk prices. You only pay — at normal checkout — if the group succeeds." />
      <Status loading={loading} error={error} onRetry={reload} />
      {data && data.items.length === 0 && <p className="text-sm text-gray-500">No open group buys right now.</p>}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {data?.items.map((c) => (
          <CampaignCard key={c.id} c={c} onChange={(n) => setData({ ...data, items: data.items.map((x) => (x.id === n.id ? n : x)) })} />
        ))}
      </div>
    </div>
  );
}
