import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiClient } from "@/lib/api/client";
import type { Retailer } from "@/types";
import { ArrowRight, Star, Store } from "lucide-react";

export const revalidate = 0;

export default async function RetailersPage() {
  let retailers: Retailer[] = [];
  try {
    retailers = await apiClient.getRetailers();
  } catch (err) {
    console.error("Failed to load retailers:", err);
  }

  return (
    <div className="container mx-auto px-4 py-10 sm:px-6 space-y-8">
      <div className="space-y-2 border-b pb-6">
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-xs text-emerald-600 border-emerald-600/30">
            Retail Network
          </Badge>
          <span className="text-xs text-muted-foreground">Pan-India Verified Partners</span>
        </div>
        <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">
          Onboarded Retail Partners
        </h1>
        <p className="text-sm text-muted-foreground max-w-2xl">
          BASKET aggregates listings and live inventory from leading brick-and-mortar and direct-to-consumer retailers across India.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {retailers.map((ret) => (
          <Card key={ret.id} className="flex flex-col justify-between overflow-hidden border transition-all hover:shadow-md">
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center space-x-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-600/10 text-emerald-700 dark:text-emerald-400 font-bold text-lg">
                    {ret.name.charAt(0)}
                  </div>
                  <div>
                    <CardTitle className="text-base font-bold">
                      {ret.name}
                    </CardTitle>
                    <div className="flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400 font-semibold mt-0.5">
                      <Star className="h-3 w-3 fill-amber-500" />
                      <span>{ret.rating.toFixed(1)} Partner Rating</span>
                    </div>
                  </div>
                </div>
                <Badge variant="secondary" className="text-[10px] bg-emerald-600/10 text-emerald-700 border-emerald-600/20">
                  Verified
                </Badge>
              </div>
            </CardHeader>

            <CardContent className="space-y-4 pt-1">
              {ret.description && (
                <p className="text-xs text-muted-foreground leading-relaxed">
                  {ret.description}
                </p>
              )}

              <div className="pt-2 border-t">
                <Link href={`/products?retailer_id=${ret.id}`} className="w-full block">
                  <Button variant="outline" size="sm" className="w-full text-xs font-semibold justify-between">
                    <span>Browse Retailer Products</span>
                    <ArrowRight className="h-3.5 w-3.5 ml-1" />
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
