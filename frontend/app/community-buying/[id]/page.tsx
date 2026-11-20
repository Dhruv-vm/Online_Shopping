"use client";

import { useParams } from "next/navigation";
import { getCampaign } from "@/lib/api/phase3";
import { CampaignCard } from "@/components/phase3/campaign-card";
import { Status, useLoad } from "@/components/phase3/kit";

export default function CampaignDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data, setData, loading, error, reload } = useLoad(() => getCampaign(id), [id]);
  return (
    <div className="container mx-auto max-w-lg px-4 py-8">
      <Status loading={loading} error={error} onRetry={reload} />
      {data && <CampaignCard c={data} onChange={setData} />}
    </div>
  );
}
