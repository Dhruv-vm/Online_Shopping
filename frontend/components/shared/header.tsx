"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Bell,
  CheckCheck,
  ChevronDown,
  LayoutDashboard,
  LogOut,
  MapPin,
  Menu,
  Search,
  ShieldCheck,
  ShoppingCart,
  User,
  X,
} from "lucide-react";
import { BasketLogo } from "@/components/brand/logo";
import { apiClient } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/auth-context";
import { canShop, homeForRole } from "@/lib/auth/roles";
import { useCart } from "@/lib/cart/cart-context";
import { useCompare } from "@/lib/compare/compare-context";
import { LanguageSwitcher, useI18n } from "@/lib/i18n/i18n-context";
import { getPincode, isValidPincode, PINCODE_EVENT, setPincode } from "@/lib/location";
import type { CustomerNotification } from "@/types/index";
import { useLiveUpdates } from "@/lib/realtime";

type NavItem = { href: string; key: string; badge?: string };

const BROWSE: NavItem[] = [
  { href: "/", key: "nav.home" },
  { href: "/products", key: "nav.catalogue" },
  { href: "/categories", key: "nav.categories" },
  { href: "/retailers", key: "nav.retailers" },
  { href: "/sale-stream", key: "nav.saleStream" },
];

const MARKETPLACE: NavItem[] = [
  { href: "/community-buying", key: "nav.communityBuying" },
  { href: "/exchange", key: "nav.exchange" },
  { href: "/auctions", key: "nav.auctions" },
  { href: "/assistant", key: "nav.assistant" },
  { href: "/list-to-basket", key: "nav.listToBasket" },
  { href: "/missions", key: "nav.missions" },
];

const CUSTOMER_EXTRA: NavItem[] = [
  { href: "/orders", key: "nav.orders" },
  { href: "/compare", key: "nav.compare" },
];

function LocationPicker() {
  const { t } = useI18n();
  const [pin, setPin] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setPin(getPincode());
    const on = (e: Event) => setPin((e as CustomEvent<string | null>).detail ?? null);
    window.addEventListener(PINCODE_EVENT, on);
    return () => window.removeEventListener(PINCODE_EVENT, on);
  }, []);

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => {
          setDraft(pin ?? "");
          setError(null);
          setOpen((o) => !o);
        }}
        className="flex items-center gap-1.5 rounded-md px-2 py-1.5 text-left text-xs hover:bg-muted"
        aria-expanded={open}
      >
        <MapPin className="h-4 w-4 text-brand" aria-hidden />
        <span className="leading-tight">
          <span className="block text-[10px] text-muted-foreground">{t("location.deliverTo")}</span>
          <span className="font-semibold">{pin ?? t("location.setPincode")}</span>
        </span>
      </button>
      {open && (
        <form
          className="absolute left-0 top-full z-50 mt-1 w-64 rounded-lg border bg-background p-3 shadow-lg"
          onSubmit={(e) => {
            e.preventDefault();
            if (!isValidPincode(draft)) {
              setError(t("location.invalid"));
              return;
            }
            setPincode(draft.trim());
            setOpen(false);
          }}
        >
          <label className="text-xs font-medium" htmlFor="hdr-pincode">
            {t("location.label")}
          </label>
          <div className="mt-1.5 flex gap-2">
            <input
              id="hdr-pincode"
              inputMode="numeric"
              maxLength={6}
              value={draft}
              onChange={(e) => setDraft(e.target.value.replace(/\D/g, ""))}
              className="h-9 w-full rounded-md border px-2 text-sm"
              placeholder="560038"
            />
            <button type="submit" className="h-9 rounded-md bg-brand px-3 text-sm font-semibold text-white">
              {t("common.apply")}
            </button>
          </div>
          {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
          <p className="mt-2 text-[11px] text-muted-foreground">{t("location.help")}</p>
          {pin && (
            <button
              type="button"
              className="mt-2 text-xs text-muted-foreground underline"
              onClick={() => {
                setPincode(null);
                setOpen(false);
              }}
            >
              {t("location.clear")}
            </button>
          )}
        </form>
      )}
    </div>
  );
}

function Notifications() {
  const { t, date } = useI18n();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<CustomerNotification[]>([]);
  const [unread, setUnread] = useState(0);
  const ref = useRef<HTMLDivElement>(null);
  const [liveTick, setLiveTick] = useState(0);
  useLiveUpdates(
    ["order.", "payment.", "fulfilment.", "auction.", "demand.", "negotiation.", "group_buy.", "exchange."],
    () => setLiveTick((n) => n + 1),
    { fallbackMs: 0 },
  );

  useEffect(() => {
    let alive = true;
    const tick = () =>
      apiClient
        .getUnreadNotificationCount()
        .then((r) => alive && setUnread(r.unread_count || 0))
        .catch(() => undefined);
    tick();
    const id = setInterval(tick, 30000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [liveTick]);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        aria-label={t("nav.notifications")}
        className="relative rounded-md p-2 hover:bg-muted"
        onClick={() => {
          const next = !open;
          setOpen(next);
          if (next)
            apiClient
              .listNotifications(15, 0)
              .then((r) => {
                setItems(r.items || []);
                setUnread(r.unread_count || 0);
              })
              .catch(() => undefined);
        }}
      >
        <Bell className="h-5 w-5" />
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-brand px-1 text-[10px] font-bold text-white">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 top-full z-50 mt-2 w-80 max-w-[90vw] overflow-hidden rounded-lg border bg-background shadow-lg">
          <div className="flex items-center justify-between border-b px-4 py-2.5">
            <span className="text-sm font-semibold">{t("nav.notifications")}</span>
            <button type="button" onClick={() => setOpen(false)} aria-label={t("common.close")}>
              <X className="h-4 w-4" />
            </button>
          </div>
          <ul className="max-h-96 overflow-y-auto">
            {items.length === 0 ? (
              <li className="px-4 py-6 text-center text-sm text-muted-foreground">{t("header.noNotifications")}</li>
            ) : (
              items.map((n) => (
                <li key={n.id} className={`border-b px-4 py-3 text-sm ${n.is_read ? "" : "bg-brand-light/60"}`}>
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-medium">{n.title}</p>
                    {!n.is_read && (
                      <button
                        type="button"
                        title={t("header.markRead")}
                        aria-label={t("header.markRead")}
                        onClick={() =>
                          apiClient
                            .markNotificationAsRead(n.id)
                            .then(() => {
                              setItems((p) => p.map((x) => (x.id === n.id ? { ...x, is_read: true } : x)));
                              setUnread((c) => Math.max(0, c - 1));
                            })
                            .catch(() => undefined)
                        }
                      >
                        <CheckCheck className="h-4 w-4 text-brand" />
                      </button>
                    )}
                  </div>
                  <p className="mt-0.5 text-xs text-muted-foreground">{n.message}</p>
                  <p className="mt-1 text-[10px] text-muted-foreground">{date(n.created_at, "datetime")}</p>
                  {n.order_id && (
                    <Link href={`/orders/${n.order_id}`} className="mt-1 inline-block text-xs text-brand underline" onClick={() => setOpen(false)}>
                      {t("header.viewOrder")}
                    </Link>
                  )}
                </li>
              ))
            )}
          </ul>
        </div>
      )}
    </div>
  );
}

export function Header() {
  const router = useRouter();
  const pathname = usePathname();
  const { user, isAuthenticated, logout } = useAuth();
  const { totalQuantity } = useCart();
  const { compareCount } = useCompare();
  const { t } = useI18n();
  const [q, setQ] = useState("");
  const [mobile, setMobile] = useState(false);
  const [marketOpen, setMarketOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const role = user?.role ?? null;
  const shopper = canShop(role);

  useEffect(() => {
    setMobile(false);
    setMarketOpen(false);
    setAccountOpen(false);
  }, [pathname]);

  const submitSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (q.trim()) router.push(`/search?q=${encodeURIComponent(q.trim())}`);
  };

  const signOut = async () => {
    await logout();
    router.push("/");
  };

  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname?.startsWith(href));
  const navLinks: NavItem[] = [...BROWSE, ...(role === "customer" ? CUSTOMER_EXTRA : [{ href: "/compare", key: "nav.compare" }])];

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/85">
      <div className="container-page flex h-16 items-center gap-3">
        <button
          type="button"
          className="rounded-md p-2 lg:hidden"
          aria-label={t("nav.menu")}
          onClick={() => setMobile((m) => !m)}
        >
          {mobile ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
        <BasketLogo tagline={t("header.tagline")} />
        <div className="hidden md:block">
          <LocationPicker />
        </div>

        <form onSubmit={submitSearch} className="relative mx-2 hidden flex-1 md:flex" role="search">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={t("common.searchPlaceholder")}
            aria-label={t("common.search")}
            className="h-10 w-full rounded-lg border border-border bg-surface pl-9 pr-3 text-sm focus:border-brand focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand/30"
          />
        </form>

        <div className="ml-auto flex items-center gap-1 sm:gap-2">
          <div className="hidden sm:block">
            <LanguageSwitcher />
          </div>
          {isAuthenticated && <Notifications />}
          {shopper && (
            <Link href="/cart" className="relative flex items-center gap-1.5 rounded-md p-2 hover:bg-muted" aria-label={t("nav.cart")}>
              <ShoppingCart className="h-5 w-5" />
              <span className="hidden text-sm font-medium xl:inline">{t("nav.cart")}</span>
              {totalQuantity > 0 && (
                <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-brand-yellow px-1 text-[10px] font-bold text-charcoal">
                  {totalQuantity}
                </span>
              )}
            </Link>
          )}
          {role === "retailer" && (
            <Link href="/retailer" className="hidden items-center gap-1.5 rounded-md bg-brand-dark px-3 py-2 text-xs font-semibold text-white sm:flex">
              <LayoutDashboard className="h-4 w-4" /> {t("nav.retailerPortal")}
            </Link>
          )}
          {role === "admin" && (
            <Link href="/admin" className="hidden items-center gap-1.5 rounded-md bg-charcoal px-3 py-2 text-xs font-semibold text-white sm:flex">
              <ShieldCheck className="h-4 w-4" /> {t("nav.adminPanel")}
            </Link>
          )}
          {isAuthenticated ? (
            <div className="relative">
              <button
                type="button"
                onClick={() => setAccountOpen((o) => !o)}
                className="flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-sm hover:bg-muted"
                aria-expanded={accountOpen}
              >
                <User className="h-4 w-4" />
                <span className="hidden max-w-[8rem] truncate sm:inline">{user?.full_name?.split(" ")[0] ?? t("nav.account")}</span>
                <ChevronDown className="h-3.5 w-3.5" />
              </button>
              {accountOpen && (
                <div className="absolute right-0 top-full z-50 mt-2 w-56 overflow-hidden rounded-lg border bg-background py-1 shadow-lg">
                  <p className="truncate px-4 py-2 text-xs text-muted-foreground">{user?.email}</p>
                  <Link href={homeForRole(role)} className="block px-4 py-2 text-sm hover:bg-muted">
                    {role === "customer" ? t("nav.account") : role === "retailer" ? t("nav.retailerPortal") : t("nav.adminPanel")}
                  </Link>
                  {role === "customer" && (
                    <>
                      <Link href="/account" className="block px-4 py-2 text-sm hover:bg-muted">{t("nav.account")}</Link>
                      <Link href="/orders" className="block px-4 py-2 text-sm hover:bg-muted">{t("nav.orders")}</Link>
                      <Link href="/account/price-alerts" className="block px-4 py-2 text-sm hover:bg-muted">{t("nav.priceAlerts")}</Link>
                      <Link href="/account/requests" className="block px-4 py-2 text-sm hover:bg-muted">{t("nav.myRequests")}</Link>
                      <Link href="/account/addresses" className="block px-4 py-2 text-sm hover:bg-muted">{t("nav.addresses")}</Link>
                    </>
                  )}
                  <button type="button" onClick={signOut} className="flex w-full items-center gap-2 px-4 py-2 text-left text-sm text-red-700 hover:bg-muted">
                    <LogOut className="h-4 w-4" /> {t("nav.logout")}
                  </button>
                </div>
              )}
            </div>
          ) : (
            <Link href="/login" className="rounded-md bg-brand px-3 py-2 text-sm font-semibold text-white hover:bg-brand/90">
              {t("nav.signIn")}
            </Link>
          )}
        </div>
      </div>

      {/* Desktop navigation row */}
      <nav className="hidden border-t lg:block" aria-label={t("nav.primary")}>
        <div className="container-page flex h-11 items-center gap-1 text-sm">
          {navLinks.map((n) => (
            <Link
              key={n.href}
              href={n.href}
              className={`rounded-md px-3 py-1.5 font-medium transition-colors ${isActive(n.href) ? "bg-brand-light text-brand-dark" : "text-charcoal/80 hover:bg-muted"}`}
            >
              {t(n.key)}
              {n.href === "/compare" && compareCount > 0 && (
                <span className="ml-1 rounded-full bg-brand px-1.5 text-[10px] text-white">{compareCount}</span>
              )}
            </Link>
          ))}
          <div className="relative">
            <button
              type="button"
              onClick={() => setMarketOpen((o) => !o)}
              className="flex items-center gap-1 rounded-md px-3 py-1.5 font-medium text-charcoal/80 hover:bg-muted"
              aria-expanded={marketOpen}
            >
              {t("nav.marketplace")} <ChevronDown className="h-3.5 w-3.5" />
            </button>
            {marketOpen && (
              <div className="absolute left-0 top-full z-50 mt-1 grid w-72 gap-0.5 rounded-lg border bg-background p-2 shadow-lg">
                {MARKETPLACE.map((m) => (
                  <Link key={m.href} href={m.href} className="rounded-md px-3 py-2 hover:bg-muted">
                    <span className="block text-sm font-medium">{t(m.key)}</span>
                    <span className="block text-xs text-muted-foreground">{t(`${m.key}.hint`)}</span>
                  </Link>
                ))}
              </div>
            )}
          </div>
          {!isAuthenticated && (
            <Link href="/register/retailer" className="ml-auto rounded-md px-3 py-1.5 text-sm font-medium text-brand-dark hover:bg-brand-light">
              {t("nav.sellOnBasket")}
            </Link>
          )}
        </div>
      </nav>

      {/* Mobile drawer */}
      {mobile && (
        <div className="border-t bg-white lg:hidden">
          <div className="container-page space-y-3 py-3">
            <form onSubmit={submitSearch} role="search" className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                type="search"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder={t("common.searchPlaceholder")}
                aria-label={t("common.search")}
                className="h-10 w-full rounded-lg border bg-surface pl-9 pr-3 text-sm"
              />
            </form>
            <div className="flex items-center justify-between">
              <LocationPicker />
              <LanguageSwitcher compact />
            </div>
            <div className="grid grid-cols-2 gap-1">
              {[...navLinks, ...MARKETPLACE].map((n) => (
                <Link key={n.href} href={n.href} className={`rounded-md px-3 py-2 text-sm ${isActive(n.href) ? "bg-brand-light font-semibold text-brand-dark" : "hover:bg-muted"}`}>
                  {t(n.key)}
                </Link>
              ))}
            </div>
            {role === "retailer" && (
              <Link href="/retailer" className="block rounded-md bg-brand-dark px-3 py-2 text-center text-sm font-semibold text-white">{t("nav.retailerPortal")}</Link>
            )}
            {role === "admin" && (
              <Link href="/admin" className="block rounded-md bg-charcoal px-3 py-2 text-center text-sm font-semibold text-white">{t("nav.adminPanel")}</Link>
            )}
            {!isAuthenticated && (
              <div className="grid grid-cols-2 gap-2">
                <Link href="/login" className="rounded-md bg-brand px-3 py-2 text-center text-sm font-semibold text-white">{t("nav.signIn")}</Link>
                <Link href="/register" className="rounded-md border px-3 py-2 text-center text-sm font-semibold">{t("nav.register")}</Link>
              </div>
            )}
          </div>
        </div>
      )}
    </header>
  );
}
