"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth/auth-context";
import { canShop, homeForRole } from "@/lib/auth/roles";
import { useI18n } from "@/lib/i18n/i18n-context";

/**
 * Retailer and admin sessions never act as a customer checkout session. They
 * see an explanation and a link back to their portal instead of the cart.
 */
export function ShopperGuard({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const { t } = useI18n();
  if (user && !canShop(user.role)) {
    return (
      <div className="container-page max-w-xl py-16 text-center">
        <h1 className="text-2xl font-bold">{t("guard.title")}</h1>
        <p className="mt-2 text-sm text-muted-foreground">{t("guard.body", { role: t(`role.${user.role}`) })}</p>
        <Link href={homeForRole(user.role)} className="mt-6 inline-block rounded-lg bg-brand px-4 py-2.5 text-sm font-semibold text-white">
          {user.role === "admin" ? t("nav.adminPanel") : t("nav.retailerPortal")}
        </Link>
      </div>
    );
  }
  return <>{children}</>;
}
