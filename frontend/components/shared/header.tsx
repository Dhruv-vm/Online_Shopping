"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  ArrowRight,
  Bell,
  CheckCheck,
  ChevronDown,
  Globe,
  Heart,
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
import type { Category, CustomerNotification } from "@/types/index";
import { useWishlist } from "@/lib/wishlist/wishlist-context";
import { useLiveUpdates } from "@/lib/realtime";

type NavItem = { href: string; key: string; badge?: string };

const MARKETPLACE: NavItem[] = [
  { href: "/community-buying", key: "nav.communityBuying" },
  { href: "/exchange", key: "nav.exchange" },
  { href: "/auctions", key: "nav.auctions" },
  { href: "/assistant", key: "nav.assistant" },
  { href: "/list-to-basket", key: "nav.listToBasket" },
  { href: "/missions", key: "nav.missions" },
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

function Notifications({ dark = false }: { dark?: boolean }) {
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
        className={`press relative flex h-10 w-10 items-center justify-center rounded-full ${dark ? "text-white hover:bg-white/10" : "hover:bg-muted"}`}
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
          <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-brand-yellow px-1 text-[10px] font-bold text-ink">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 top-full z-50 mt-3 w-80 max-w-[90vw] origin-top-right animate-scale-in overflow-hidden rounded-2xl border bg-white text-ink shadow-card-hover">
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

const NAV: { href: string; key: string; match?: (p: string, q: URLSearchParams | null) => boolean }[] = [
  { href: "/", key: "nav.home", match: (p) => p === "/" },
  { href: "/sale-stream", key: "nav.deals", match: (p) => p.startsWith("/sale-stream") },
  { href: "/products?sort_by=newest", key: "nav.newArrivals", match: (p, q) => p === "/products" && q?.get("sort_by") === "newest" },
  { href: "/#the-basket-edit", key: "nav.collections" },
];

const MORE: NavItem[] = [
  { href: "/products", key: "nav.catalogue" },
  { href: "/retailers", key: "nav.retailers" },
  ...MARKETPLACE,
  { href: "/compare", key: "nav.compare" },
];

function useScrolled(offset = 12) {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const on = () => setScrolled(window.scrollY > offset);
    on();
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, [offset]);
  return scrolled;
}

/** Close a popover on outside click or Escape. */
function useDismiss(open: boolean, close: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) close();
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, close]);
  return ref;
}

function CategoriesMenu({ active }: { active: boolean }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [cats, setCats] = useState<Category[] | null>(null);
  const close = useCallback(() => setOpen(false), []);
  const ref = useDismiss(open, close);
  useEffect(() => {
    if (open && cats === null) apiClient.getCategories().then(setCats).catch(() => setCats([]));
  }, [open, cats]);
  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="true"
        className={`nav-link flex items-center gap-1 ${active ? "is-active" : ""}`}
      >
        {t("nav.categories")}
        <ChevronDown className={`h-3.5 w-3.5 transition-transform duration-base ease-out ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="absolute left-1/2 top-full z-50 mt-4 w-[34rem] -translate-x-1/2 origin-top animate-scale-in rounded-2xl border bg-white p-3 text-ink shadow-card-hover">
          <div className="grid grid-cols-2 gap-1">
            {(cats ?? []).map((c) => (
              <Link key={c.id} href={`/products?category_slug=${c.slug}`} onClick={close} className="group/c flex items-center justify-between rounded-xl px-3 py-2.5 text-sm font-semibold transition-colors duration-base hover:bg-brand-light">
                {c.name}
                <ArrowRight className="h-4 w-4 -translate-x-1 opacity-0 transition-all duration-base ease-out group-hover/c:translate-x-0 group-hover/c:opacity-100" />
              </Link>
            ))}
            {cats === null && <p className="col-span-2 px-3 py-6 text-center text-sm text-muted-foreground">{t("common.loading")}</p>}
          </div>
          <Link href="/categories" onClick={close} className="mt-2 flex items-center justify-center gap-1.5 rounded-xl bg-ink px-3 py-2.5 text-sm font-semibold text-white">
            {t("header.allCategories")} <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      )}
    </div>
  );
}

function MoreMenu() {
  const { t } = useI18n();
  const { compareCount } = useCompare();
  const [open, setOpen] = useState(false);
  const close = useCallback(() => setOpen(false), []);
  const ref = useDismiss(open, close);
  return (
    <div className="relative" ref={ref}>
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-haspopup="true" className="nav-link flex items-center gap-1">
        {t("nav.more")}
        <ChevronDown className={`h-3.5 w-3.5 transition-transform duration-base ease-out ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="absolute left-1/2 top-full z-50 mt-4 grid w-80 -translate-x-1/2 origin-top animate-scale-in gap-0.5 rounded-2xl border bg-white p-2 text-ink shadow-card-hover">
          {MORE.map((m) => (
            <Link key={m.href} href={m.href} onClick={close} className="rounded-xl px-3 py-2 transition-colors duration-base hover:bg-brand-light">
              <span className="flex items-center gap-2 text-sm font-semibold">
                {t(m.key)}
                {m.href === "/compare" && compareCount > 0 && <span className="rounded-full bg-ink px-1.5 text-[10px] text-white">{compareCount}</span>}
              </span>
              {m.key !== "nav.catalogue" && m.key !== "nav.retailers" && m.key !== "nav.compare" && (
                <span className="block text-xs text-muted-foreground">{t(`${m.key}.hint`)}</span>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function PreferencesMenu() {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const close = useCallback(() => setOpen(false), []);
  const ref = useDismiss(open, close);
  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-label={t("header.preferences")}
        title={t("header.preferences")}
        className="press flex h-10 w-10 items-center justify-center rounded-full text-white hover:bg-white/10"
      >
        <Globe className="h-5 w-5" />
      </button>
      {open && (
        <div className="absolute right-0 top-full z-50 mt-3 w-72 origin-top-right animate-scale-in space-y-3 rounded-2xl border bg-white p-4 text-ink shadow-card-hover">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{t("header.preferences")}</p>
          <LocationPicker />
          <LanguageSwitcher />
        </div>
      )}
    </div>
  );
}

/** Cart icon with a count that pops and a cart that bumps when items are added. */
function CartButton() {
  const { t } = useI18n();
  const { totalQuantity } = useCart();
  const prev = useRef(totalQuantity);
  const [bump, setBump] = useState(0);
  useEffect(() => {
    if (totalQuantity > prev.current) setBump((b) => b + 1);
    prev.current = totalQuantity;
  }, [totalQuantity]);
  return (
    <Link href="/cart" id="header-cart" className="press relative flex h-10 w-10 items-center justify-center rounded-full text-white hover:bg-white/10" aria-label={`${t("nav.cart")}${totalQuantity ? ` (${totalQuantity})` : ""}`}>
      <ShoppingCart key={`c${bump}`} className={`h-5 w-5 ${bump ? "animate-cart-bump" : ""}`} />
      {totalQuantity > 0 && (
        <span key={`b${totalQuantity}`} className="absolute right-0.5 top-0.5 flex h-[18px] min-w-[18px] animate-badge-pop items-center justify-center rounded-full bg-brand-yellow px-1 text-[10px] font-bold text-ink ring-2 ring-ink">
          {totalQuantity > 99 ? "99+" : totalQuantity}
        </span>
      )}
    </Link>
  );
}

function WishlistButton() {
  const { t } = useI18n();
  const { count } = useWishlist();
  return (
    <Link href="/wishlist" className="press relative flex h-10 w-10 items-center justify-center rounded-full text-white hover:bg-white/10" aria-label={`${t("nav.wishlist")}${count ? ` (${count})` : ""}`}>
      <Heart className="h-5 w-5" />
      {count > 0 && (
        <span key={count} className="absolute right-0.5 top-0.5 flex h-[18px] min-w-[18px] animate-badge-pop items-center justify-center rounded-full bg-white px-1 text-[10px] font-bold text-ink ring-2 ring-ink">
          {count}
        </span>
      )}
    </Link>
  );
}

function AccountMenu() {
  const router = useRouter();
  const { t } = useI18n();
  const { user, isAuthenticated, logout } = useAuth();
  const role = user?.role ?? null;
  const [open, setOpen] = useState(false);
  const close = useCallback(() => setOpen(false), []);
  const ref = useDismiss(open, close);
  if (!isAuthenticated) {
    return (
      <Link href="/login" className="press flex h-10 items-center gap-1.5 whitespace-nowrap rounded-full bg-brand-yellow px-4 text-sm font-semibold text-ink hover:bg-brand-yellow-dark" aria-label={t("nav.signIn")}>
        <User className="h-4 w-4" /> <span className="hidden sm:inline">{t("nav.signIn")}</span>
      </Link>
    );
  }
  const item = "block rounded-xl px-3 py-2 text-sm transition-colors duration-base hover:bg-brand-light";
  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="true"
        aria-label={t("nav.account")}
        className="press flex h-10 w-10 items-center justify-center rounded-full text-white ring-1 ring-white/25 hover:bg-white/10"
      >
        <span className="text-sm font-bold uppercase">{(user?.full_name || user?.email || "?").trim().charAt(0)}</span>
      </button>
      {open && (
        <div className="absolute right-0 top-full z-50 mt-3 w-60 origin-top-right animate-scale-in rounded-2xl border bg-white p-2 text-ink shadow-card-hover">
          <p className="truncate px-3 pb-2 pt-1 text-xs text-muted-foreground">{user?.email}</p>
          <Link href={homeForRole(role)} onClick={close} className={`${item} font-semibold`}>
            {role === "customer" ? t("nav.account") : role === "retailer" ? t("nav.retailerPortal") : t("nav.adminPanel")}
          </Link>
          {role === "customer" && (
            <>
              <Link href="/orders" onClick={close} className={item}>{t("nav.orders")}</Link>
              <Link href="/wishlist" onClick={close} className={item}>{t("nav.wishlist")}</Link>
              <Link href="/account/price-alerts" onClick={close} className={item}>{t("nav.priceAlerts")}</Link>
              <Link href="/account/requests" onClick={close} className={item}>{t("nav.myRequests")}</Link>
              <Link href="/account/addresses" onClick={close} className={item}>{t("nav.addresses")}</Link>
            </>
          )}
          <button
            type="button"
            onClick={async () => {
              close();
              await logout();
              router.push("/");
            }}
            className="mt-1 flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm text-red-700 transition-colors duration-base hover:bg-red-50"
          >
            <LogOut className="h-4 w-4" /> {t("nav.logout")}
          </button>
        </div>
      )}
    </div>
  );
}

export function Header() {
  const router = useRouter();
  const pathname = usePathname() || "/";
  const params = useSearchParams();
  const { user, isAuthenticated } = useAuth();
  const { t } = useI18n();
  const [q, setQ] = useState("");
  const [mobile, setMobile] = useState(false);
  const scrolled = useScrolled();
  const role = user?.role ?? null;
  const shopper = canShop(role);

  useEffect(() => setMobile(false), [pathname]);

  const submitSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (q.trim()) router.push(`/search?q=${encodeURIComponent(q.trim())}`);
  };
  const isActive = (n: (typeof NAV)[number]) => (n.match ? n.match(pathname, params) : false);
  const categoriesActive = pathname.startsWith("/categories") || (pathname === "/products" && !!params?.get("category_slug"));

  const search = (id: string, extra = "") => (
    <form onSubmit={submitSearch} role="search" className={`group/s relative ${extra}`}>
      <label htmlFor={id} className="sr-only">{t("common.search")}</label>
      <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-white/55 transition-colors duration-base group-focus-within/s:text-brand-yellow" />
      <input
        id={id}
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder={t("common.searchPlaceholder")}
        className="h-10 w-full rounded-full border border-white/10 bg-white/[0.08] pl-10 pr-4 text-sm text-white placeholder:text-white/50 transition-[background-color,border-color,box-shadow] duration-base ease-out focus:border-brand-yellow/70 focus:bg-white/[0.12] focus:outline-none focus:ring-2 focus:ring-brand-yellow/25"
      />
    </form>
  );

  return (
    <header className={`sticky top-0 z-50 w-full transition-[padding] duration-slow ease-out ${scrolled ? "pt-2" : "pt-3"}`}>
      <div className="container-page">
        <div className={`flex items-center gap-2 rounded-full bg-ink pl-4 pr-2 text-white shadow-nav transition-[height] duration-slow ease-out sm:pl-6 ${scrolled ? "h-14" : "h-16"}`}>
          <button
            type="button"
            className="press -ml-1 flex h-10 w-10 items-center justify-center rounded-full hover:bg-white/10 lg:hidden"
            aria-label={t("nav.menu")}
            aria-expanded={mobile}
            onClick={() => setMobile((m) => !m)}
          >
            {mobile ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
          <BasketLogo height={30} priority />

          <nav className="ml-4 hidden items-center lg:flex xl:ml-8" aria-label={t("nav.primary")}>
            <Link href="/" className={`nav-link ${isActive(NAV[0]) ? "is-active" : ""}`} aria-current={isActive(NAV[0]) ? "page" : undefined}>{t("nav.home")}</Link>
            <CategoriesMenu active={categoriesActive} />
            {NAV.slice(1).map((n) => (
              <Link key={n.href} href={n.href} className={`nav-link ${isActive(n) ? "is-active" : ""}`} aria-current={isActive(n) ? "page" : undefined}>
                {t(n.key)}
              </Link>
            ))}
            <MoreMenu />
          </nav>

          {search("hdr-search", "ml-auto hidden w-full min-w-0 max-w-[13rem] md:block xl:max-w-[17rem] 2xl:max-w-xs")}

          <div className="ml-auto flex items-center gap-0.5 md:ml-2">
            <div className="hidden sm:block"><PreferencesMenu /></div>
            {shopper && <WishlistButton />}
            {shopper && <CartButton />}
            {isAuthenticated && <Notifications dark />}
            {role === "retailer" && (
              <Link href="/retailer" className="press mx-1 hidden h-9 items-center gap-1.5 rounded-full bg-brand-yellow px-3 text-xs font-semibold text-ink xl:flex">
                <LayoutDashboard className="h-4 w-4" /> {t("nav.retailerPortal")}
              </Link>
            )}
            {role === "admin" && (
              <Link href="/admin" className="press mx-1 hidden h-9 items-center gap-1.5 rounded-full bg-brand-yellow px-3 text-xs font-semibold text-ink xl:flex">
                <ShieldCheck className="h-4 w-4" /> {t("nav.adminPanel")}
              </Link>
            )}
            <AccountMenu />
          </div>
        </div>

        {/* Mobile drawer */}
        {mobile && (
          <div className="mt-2 animate-fade-up rounded-3xl bg-ink p-4 text-white shadow-nav lg:hidden">
            {search("hdr-search-m")}
            <div className="mt-3 grid grid-cols-2 gap-1">
              {[{ href: "/", key: "nav.home" }, { href: "/categories", key: "nav.categories" }, ...NAV.slice(1), ...MORE].map((n) => (
                <Link key={n.href} href={n.href} className="rounded-xl px-3 py-2.5 text-sm font-medium text-white/85 transition-colors duration-base hover:bg-white/10 hover:text-white">
                  {t(n.key)}
                </Link>
              ))}
            </div>
            <div className="mt-3 space-y-3 rounded-2xl bg-white p-3 text-ink">
              <LocationPicker />
              <LanguageSwitcher compact />
            </div>
            {role === "retailer" && (
              <Link href="/retailer" className="mt-3 block rounded-full bg-brand-yellow px-3 py-2.5 text-center text-sm font-semibold text-ink">{t("nav.retailerPortal")}</Link>
            )}
            {role === "admin" && (
              <Link href="/admin" className="mt-3 block rounded-full bg-brand-yellow px-3 py-2.5 text-center text-sm font-semibold text-ink">{t("nav.adminPanel")}</Link>
            )}
            {!isAuthenticated && (
              <div className="mt-3 grid grid-cols-2 gap-2">
                <Link href="/login" className="rounded-full bg-brand-yellow px-3 py-2.5 text-center text-sm font-semibold text-ink">{t("nav.signIn")}</Link>
                <Link href="/register" className="rounded-full border border-white/25 px-3 py-2.5 text-center text-sm font-semibold">{t("nav.register")}</Link>
              </div>
            )}
            {!isAuthenticated && (
              <Link href="/register/retailer" className="mt-2 block text-center text-xs text-white/70 underline">{t("nav.sellOnBasket")}</Link>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
