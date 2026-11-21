"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { CampaignCard } from "@/components/phase3/campaign-card";
import { Status, useLoad } from "@/components/phase3/kit";
import { getCampaign } from "@/lib/api/phase3";
import { useI18n } from "@/lib/i18n/i18n-context";
import { useLiveUpdates } from "@/lib/realtime";

export default function CampaignDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { t } = useI18n();
  const campaign = useLoad(() => getCampaign(id), [id]);
  const { data, setData, loading, error, reload } = campaign;
  useLiveUpdates(["group_buy."], () => void campaign.refresh(), { match: (n) => n.id === id });
  return (
    <div className="container-page max-w-lg py-8">
      <Link href="/community-buying" className="text-sm text-brand underline">← {t("nav.communityBuying")}</Link>
      <div className="mt-4">
        <Status loading={loading} error={error} onRetry={reload} />
        {data && <CampaignCard c={data} onChange={setData} />}
      </div>
    </div>
  );
}
