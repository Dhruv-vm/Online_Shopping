"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth/auth-context";
import { User, MapPin, LogOut, ShieldCheck, Loader2, Package, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function AccountNav() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const navItems = [
    {
      title: "Account Overview",
      href: "/account",
      icon: User,
      active: pathname === "/account",
    },
    {
      title: "My Orders",
      href: "/orders",
      icon: Package,
      active: pathname === "/orders" || pathname.startsWith("/orders/"),
    },
    {
      title: "Shopping Intent & Memory",
      href: "/account/intent",
      icon: Sparkles,
      active: pathname === "/account/intent",
    },
    {
      title: "Saved Addresses",
      href: "/account/addresses",
      icon: MapPin,
      active: pathname === "/account/addresses",
    },
  ];

  const handleLogout = async () => {
    setIsLoggingOut(true);
    try {
      await logout();
      router.push("/");
    } finally {
      setIsLoggingOut(false);
    }
  };

  return (
    <aside className="w-full md:w-64 shrink-0 space-y-6">
      {/* User Mini Card */}
      <div className="rounded-xl border bg-card p-5 shadow-xs">
        <div className="flex items-center gap-3.5">
          <div className="flex h-11 w-11 items-center justify-center rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 font-bold text-lg">
            {user?.full_name ? user.full_name.charAt(0).toUpperCase() : "U"}
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-foreground text-sm truncate">
              {user?.full_name || "Valued Customer"}
            </h3>
            <p className="text-xs text-muted-foreground truncate">{user?.email}</p>
          </div>
        </div>

        <div className="mt-4 pt-3.5 border-t border-muted/60 flex items-center justify-between text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5 text-emerald-700 dark:text-emerald-400 font-medium">
            <ShieldCheck className="h-3.5 w-3.5" />
            Verified Customer
          </span>
          <span className="capitalize">{user?.role || "customer"}</span>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="rounded-xl border bg-card p-2 shadow-xs space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-colors",
                item.active
                  ? "bg-emerald-50 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 font-semibold"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              )}
            >
              <Icon className={cn("h-4 w-4 shrink-0", item.active ? "text-emerald-600 dark:text-emerald-400" : "")} />
              {item.title}
            </Link>
          );
        })}

        <div className="pt-2 border-t border-muted/50">
          <Button
            variant="ghost"
            onClick={handleLogout}
            disabled={isLoggingOut}
            className="w-full justify-start gap-3 px-3.5 py-2.5 h-auto text-sm font-medium text-red-600 dark:text-red-400 hover:bg-red-50 hover:text-red-700 dark:hover:bg-red-950/40"
          >
            {isLoggingOut ? (
              <Loader2 className="h-4 w-4 animate-spin shrink-0" />
            ) : (
              <LogOut className="h-4 w-4 shrink-0" />
            )}
            Sign Out
          </Button>
        </div>
      </nav>
    </aside>
  );
}
