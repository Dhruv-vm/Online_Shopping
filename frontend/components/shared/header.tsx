"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ShoppingBasket,
  Search,
  Menu,
  X,
  Store,
  LayoutGrid,
  User,
  LogOut,
  MapPin,
  ShoppingCart,
  Package,
  Bell,
  Check,
  CheckCheck,
  Scale,
  ShieldAlert,
  Compass,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/lib/auth/auth-context";
import { useCart } from "@/lib/cart/cart-context";
import { useCompare } from "@/lib/compare/compare-context";
import { LanguageSwitcher, useI18n } from "@/lib/i18n/i18n-context";
import { apiClient } from "@/lib/api/client";
import type { CustomerNotification } from "@/types/index";

export function Header() {
  const router = useRouter();
  const { user, isAuthenticated, isLoading, logout } = useAuth();
  const { totalQuantity } = useCart();
  const { compareCount } = useCompare();
  const { t } = useI18n();
  const [searchQuery, setSearchQuery] = useState("");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [notifications, setNotifications] = useState<CustomerNotification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const notifRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let mounted = true;
    const fetchNotifications = async () => {
      try {
        const countRes = await apiClient.getUnreadNotificationCount();
        if (mounted) setUnreadCount(countRes.unread_count || 0);
      } catch {
        // Guest or unauthenticated background fetch ignored
      }
    };
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 30000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, [isAuthenticated]);

  const loadNotifications = async () => {
    try {
      const res = await apiClient.listNotifications(15, 0);
      setNotifications(res.items || []);
      setUnreadCount(res.unread_count || 0);
    } catch {
      // Fallback gracefully
    }
  };

  const toggleNotifications = () => {
    const nextState = !notificationsOpen;
    setNotificationsOpen(nextState);
    if (nextState) {
      loadNotifications();
    }
  };

  const handleMarkAsRead = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await apiClient.markNotificationAsRead(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      );
      setUnreadCount((c) => Math.max(0, c - 1));
    } catch {
      // Ignore
    }
  };

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setNotificationsOpen(false);
      }
    };
    if (notificationsOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [notificationsOpen]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      router.push(`/search?q=${encodeURIComponent(searchQuery.trim())}`);
      setMobileMenuOpen(false);
    }
  };

  const handleLogout = async () => {
    await logout();
    setMobileMenuOpen(false);
    router.push("/");
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80 shadow-xs">
      <div className="container mx-auto flex h-16 items-center justify-between px-4 sm:px-6 gap-4">
        {/* Brand Logo */}
        <Link href="/" className="flex items-center space-x-2.5 shrink-0">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-600 text-white shadow-sm">
            <ShoppingBasket className="h-5 w-5" />
          </div>
          <div className="flex flex-col">
            <div className="flex items-center">
              <span className="text-xl font-extrabold tracking-tight text-foreground">
                BASKET
              </span>
              <Badge variant="outline" className="ml-2 font-mono text-[10px] text-emerald-700 dark:text-emerald-400 border-emerald-600/30">
                Live Store
              </Badge>
            </div>
            <span className="text-[10px] text-muted-foreground hidden sm:block">
              Multi-Category Indian Retail
            </span>
          </div>
        </Link>

        {/* Global Search Bar (Desktop) */}
        <form
          onSubmit={handleSearchSubmit}
          className="relative hidden md:flex flex-1 max-w-md mx-4 items-center"
        >
          <Search className="absolute left-3 h-4 w-4 text-muted-foreground pointer-events-none" />
          <Input
            type="search"
            placeholder="Search Sony headphones, FabIndia silk, organic groceries..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9 pr-4 h-10 w-full bg-muted/40 border-muted-foreground/20 focus:bg-background transition-colors text-xs sm:text-sm"
          />
        </form>

        {/* Desktop Navigation Links */}
        <nav className="hidden lg:flex items-center space-x-5 text-sm font-medium">
          <Link
            href="/products"
            className="flex items-center gap-1.5 text-muted-foreground transition-colors hover:text-emerald-700 dark:hover:text-emerald-400"
          >
            <LayoutGrid className="h-4 w-4" />
            Catalogue
          </Link>
          <Link
            href="/categories"
            className="text-muted-foreground transition-colors hover:text-emerald-700 dark:hover:text-emerald-400"
          >
            Categories
          </Link>
          <Link
            href="/retailers"
            className="flex items-center gap-1.5 text-muted-foreground transition-colors hover:text-emerald-700 dark:hover:text-emerald-400"
          >
            <Store className="h-4 w-4" />
            Retailers
          </Link>

          {/* Orders Link (Desktop) */}
          <Link
            href="/orders"
            className="flex items-center gap-1.5 text-muted-foreground transition-colors hover:text-emerald-700 dark:hover:text-emerald-400"
          >
            <Package className="h-4 w-4" />
            Orders
          </Link>

          {/* Phase 3: Sale Stream (Desktop) */}
          <Link
            href="/sale-stream"
            className="text-muted-foreground transition-colors hover:text-emerald-700 dark:hover:text-emerald-400"
          >
            {t("nav.saleStream")}
          </Link>

          {/* Basket Mission Link (Desktop) */}
          <Link
            href="/missions"
            className="flex items-center gap-1.5 text-muted-foreground transition-colors hover:text-emerald-700 dark:hover:text-emerald-400 group"
          >
            <Compass className="h-4 w-4 text-emerald-600 group-hover:rotate-45 transition-transform" />
            <span>Missions</span>
            <Badge variant="secondary" className="text-[10px] py-0 px-1.5 bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 font-semibold">
              New
            </Badge>
          </Link>

          {/* Compare Link (Desktop) */}
          <Link
            href="/compare"
            className="flex items-center gap-1.5 text-muted-foreground transition-colors hover:text-emerald-700 dark:hover:text-emerald-400 relative"
          >
            <Scale className="h-4 w-4" />
            Compare
            {compareCount > 0 && (
              <span className="flex h-4 min-w-4 items-center justify-center rounded-full bg-emerald-600 px-1 text-[10px] font-bold text-white shadow-xs">
                {compareCount}
              </span>
            )}
          </Link>

          {/* Notification Center Popover Trigger */}
          <div className="relative" ref={notifRef}>
            <button
              type="button"
              onClick={toggleNotifications}
              className="relative p-2 text-muted-foreground transition-colors hover:text-emerald-700 dark:hover:text-emerald-400 focus:outline-none"
              aria-label="Notification Center"
              title="Notifications"
            >
              <Bell className="h-5 w-5" />
              {unreadCount > 0 && (
                <span className="absolute top-1 right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-emerald-600 px-1 text-[10px] font-bold text-white shadow-xs">
                  {unreadCount > 9 ? "9+" : unreadCount}
                </span>
              )}
            </button>

            {/* Notification Dropdown Panel */}
            {notificationsOpen && (
              <div className="absolute right-0 mt-2 w-80 sm:w-96 rounded-xl border bg-card p-0 shadow-xl z-50 overflow-hidden text-card-foreground">
                <div className="flex items-center justify-between border-b px-4 py-3 bg-muted/30">
                  <div className="flex items-center gap-2">
                    <Bell className="h-4 w-4 text-emerald-600" />
                    <span className="text-sm font-semibold">Notifications</span>
                    {unreadCount > 0 && (
                      <Badge variant="outline" className="text-xs bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300">
                        {unreadCount} unread
                      </Badge>
                    )}
                  </div>
                  <Link
                    href="/orders"
                    onClick={() => setNotificationsOpen(false)}
                    className="text-xs text-emerald-600 hover:underline font-medium"
                  >
                    View Orders
                  </Link>
                </div>

                <div className="max-h-80 overflow-y-auto divide-y divide-muted/40">
                  {notifications.length === 0 ? (
                    <div className="p-6 text-center text-xs text-muted-foreground">
                      No notifications yet.
                    </div>
                  ) : (
                    notifications.map((notif) => (
                      <div
                        key={notif.id}
                        onClick={() => {
                          if (notif.order_id) {
                            router.push(`/orders/${notif.order_id}`);
                            setNotificationsOpen(false);
                          }
                        }}
                        className={`p-3.5 hover:bg-muted/50 cursor-pointer transition-colors flex items-start gap-3 ${
                          !notif.is_read ? "bg-emerald-50/50 dark:bg-emerald-950/20" : ""
                        }`}
                      >
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between gap-2">
                            <h4 className="text-xs font-semibold text-foreground truncate">
                              {notif.title}
                            </h4>
                            <span className="text-[10px] text-muted-foreground shrink-0">
                              {new Date(notif.created_at).toLocaleDateString("en-IN", {
                                month: "short",
                                day: "numeric",
                              })}
                            </span>
                          </div>
                          <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                            {notif.message}
                          </p>
                        </div>
                        {!notif.is_read && (
                          <button
                            type="button"
                            onClick={(e) => handleMarkAsRead(notif.id, e)}
                            title="Mark as read"
                            className="p-1 text-muted-foreground hover:text-emerald-600 shrink-0"
                          >
                            <Check className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>

          <LanguageSwitcher />

          {/* Cart Icon Link (Desktop) */}
          <Link
            href="/cart"
            className="relative flex items-center gap-1.5 text-muted-foreground transition-colors hover:text-emerald-700 dark:hover:text-emerald-400"
            aria-label="Shopping Cart"
          >
            <div className="relative">
              <ShoppingCart className="h-5 w-5" />
              {totalQuantity > 0 && (
                <span className="absolute -top-2 -right-2 flex h-4 min-w-4 items-center justify-center rounded-full bg-emerald-600 px-1 text-[10px] font-bold text-white shadow-xs">
                  {totalQuantity > 99 ? "99+" : totalQuantity}
                </span>
              )}
            </div>
            <span>Cart</span>
          </Link>

          {/* Desktop User Authentication Controls */}
          {!isLoading && (
            <div className="flex items-center gap-2.5 pl-2 border-l border-muted">
              {isAuthenticated ? (
                <div className="flex items-center gap-2">
                  {user?.role === "admin" && (
                    <Link href="/admin">
                      <Badge className="bg-purple-600 hover:bg-purple-700 text-white font-medium cursor-pointer flex items-center gap-1 text-[11px] py-1 px-2">
                        <ShieldAlert className="h-3 w-3" />
                        Admin
                      </Badge>
                    </Link>
                  )}
                  {user?.role === "retailer" && (
                    <Link href="/retailer">
                      <Badge className="bg-blue-600 hover:bg-blue-700 text-white font-medium cursor-pointer flex items-center gap-1 text-[11px] py-1 px-2">
                        <Store className="h-3 w-3" />
                        Retailer
                      </Badge>
                    </Link>
                  )}

                  <Link href="/account">
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-9 gap-2 text-xs font-semibold border-emerald-600/40 text-emerald-700 hover:bg-emerald-50 dark:text-emerald-300 dark:hover:bg-emerald-950/40"
                    >
                      <User className="h-3.5 w-3.5" />
                      {user?.full_name ? user.full_name.split(" ")[0] : "Account"}
                    </Button>
                  </Link>

                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleLogout}
                    title="Sign Out"
                    aria-label="Sign Out"
                    className="h-9 w-9 p-0 text-muted-foreground hover:text-red-600"
                  >
                    <LogOut className="h-4 w-4" />
                  </Button>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <Link
                    href="/register/retailer"
                    className="text-xs text-muted-foreground hover:text-emerald-700 dark:hover:text-emerald-400 font-medium px-2 py-1 hidden xl:block"
                  >
                    Sell on BASKET
                  </Link>
                  <Link href="/login">
                    <Button variant="ghost" size="sm" className="h-9 text-xs font-medium">
                      Sign In
                    </Button>
                  </Link>
                  <Link href="/register">
                    <Button
                      size="sm"
                      className="h-9 text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs"
                    >
                      Register
                    </Button>
                  </Link>
                </div>
              )}
            </div>
          )}
        </nav>

        {/* Mobile triggers */}
        <div className="flex items-center lg:hidden gap-1.5">
          <Link href="/cart" className="relative p-2 text-foreground" aria-label="Shopping Cart">
            <ShoppingCart className="h-5 w-5" />
            {totalQuantity > 0 && (
              <span className="absolute top-0.5 right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-emerald-600 px-1 text-[10px] font-bold text-white shadow-xs">
                {totalQuantity > 99 ? "99+" : totalQuantity}
              </span>
            )}
          </Link>

          {isAuthenticated && (
            <Link href="/account" className="sm:hidden">
              <Button
                variant="outline"
                size="sm"
                className="h-8 px-2 text-xs font-medium border-emerald-600/40 text-emerald-700"
              >
                <User className="h-3.5 w-3.5" />
              </Button>
            </Link>
          )}

          <Button
            variant="ghost"
            size="sm"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Toggle navigation"
            className="h-9 w-9 p-0"
          >
            {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </Button>
        </div>
      </div>

      {/* Mobile Navigation Drawer / Dropdown */}
      {mobileMenuOpen && (
        <div className="lg:hidden border-t bg-background px-4 py-4 space-y-4">
          <form onSubmit={handleSearchSubmit} className="relative">
            <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
            <Input
              type="search"
              placeholder="Search products, brands, categories..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 pr-4 h-10 w-full"
            />
          </form>

          <nav className="flex flex-col space-y-1 text-sm font-medium pt-1">
            <Link
              href="/cart"
              onClick={() => setMobileMenuOpen(false)}
              className="px-3 py-2 rounded-md hover:bg-muted text-foreground flex items-center justify-between"
            >
              <div className="flex items-center gap-2">
                <ShoppingCart className="h-4 w-4 text-emerald-600" />
                Shopping Cart
              </div>
              {totalQuantity > 0 && (
                <Badge className="bg-emerald-600 text-white text-xs">
                  {totalQuantity} {totalQuantity === 1 ? "item" : "items"}
                </Badge>
              )}
            </Link>
            <Link
              href="/products"
              onClick={() => setMobileMenuOpen(false)}
              className="px-3 py-2 rounded-md hover:bg-muted text-foreground flex items-center gap-2"
            >
              <LayoutGrid className="h-4 w-4 text-emerald-600" />
              Catalogue
            </Link>
            <Link
              href="/categories"
              onClick={() => setMobileMenuOpen(false)}
              className="px-3 py-2 rounded-md hover:bg-muted text-foreground"
            >
              Categories
            </Link>
            <Link
              href="/orders"
              onClick={() => setMobileMenuOpen(false)}
              className="px-3 py-2 rounded-md hover:bg-muted text-foreground flex items-center gap-2"
            >
              <Package className="h-4 w-4 text-emerald-600" />
              My Orders & Tracking
            </Link>
            {[
              ["/sale-stream", "nav.saleStream"],
              ["/community-buying", "nav.communityBuying"],
              ["/exchange", "nav.exchange"],
              ["/auctions", "nav.auctions"],
              ["/list-to-basket", "nav.listToBasket"],
            ].map(([href, key]) => (
              <Link
                key={href}
                href={href}
                onClick={() => setMobileMenuOpen(false)}
                className="px-3 py-2 rounded-md hover:bg-muted text-foreground"
              >
                {t(key)}
              </Link>
            ))}
            <div className="px-3 py-2">
              <LanguageSwitcher />
            </div>
            <Link
              href="/missions"
              onClick={() => setMobileMenuOpen(false)}
              className="px-3 py-2 rounded-md hover:bg-muted text-foreground flex items-center justify-between"
            >
              <div className="flex items-center gap-2">
                <Compass className="h-4 w-4 text-emerald-600" />
                Basket Mission
              </div>
              <Badge variant="secondary" className="text-[10px] py-0 px-1.5 bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 font-semibold">
                New
              </Badge>
            </Link>
            <Link
              href="/compare"
              onClick={() => setMobileMenuOpen(false)}
              className="px-3 py-2 rounded-md hover:bg-muted text-foreground flex items-center justify-between"
            >
              <div className="flex items-center gap-2">
                <Scale className="h-4 w-4 text-emerald-600" />
                Compare Products
              </div>
              {compareCount > 0 && (
                <Badge className="bg-emerald-600 text-white text-xs">
                  {compareCount}
                </Badge>
              )}
            </Link>
            <Link
              href="/retailers"
              onClick={() => setMobileMenuOpen(false)}
              className="px-3 py-2 rounded-md hover:bg-muted text-foreground flex items-center gap-2"
            >
              <Store className="h-4 w-4 text-emerald-600" />
              Partner Retailers
            </Link>

            <div className="pt-2 border-t border-muted/60 my-2">
              {isAuthenticated ? (
                <>
                  {user?.role === "admin" && (
                    <Link
                      href="/admin"
                      onClick={() => setMobileMenuOpen(false)}
                      className="px-3 py-2 rounded-md bg-purple-50 dark:bg-purple-950/40 text-purple-700 dark:text-purple-300 font-semibold flex items-center gap-2 mb-1"
                    >
                      <ShieldAlert className="h-4 w-4" />
                      Admin Portal
                    </Link>
                  )}
                  {user?.role === "retailer" && (
                    <Link
                      href="/retailer"
                      onClick={() => setMobileMenuOpen(false)}
                      className="px-3 py-2 rounded-md bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300 font-semibold flex items-center gap-2 mb-1"
                    >
                      <Store className="h-4 w-4" />
                      Retailer Portal
                    </Link>
                  )}
                  <Link
                    href="/account"
                    onClick={() => setMobileMenuOpen(false)}
                    className="px-3 py-2 rounded-md hover:bg-muted text-foreground flex items-center gap-2 font-semibold text-emerald-700 dark:text-emerald-400"
                  >
                    <User className="h-4 w-4" />
                    My Account ({user?.full_name})
                  </Link>
                  <Link
                    href="/account/addresses"
                    onClick={() => setMobileMenuOpen(false)}
                    className="px-3 py-2 rounded-md hover:bg-muted text-foreground flex items-center gap-2"
                  >
                    <MapPin className="h-4 w-4" />
                    Saved Addresses
                  </Link>
                  <button
                    type="button"
                    onClick={handleLogout}
                    className="w-full text-left px-3 py-2 rounded-md hover:bg-red-50 text-red-600 dark:hover:bg-red-950/40 flex items-center gap-2"
                  >
                    <LogOut className="h-4 w-4" />
                    Sign Out
                  </button>
                </>
              ) : (
                <div className="flex flex-col gap-2 pt-1">
                  <Link
                    href="/login"
                    onClick={() => setMobileMenuOpen(false)}
                    className="w-full"
                  >
                    <Button variant="outline" className="w-full justify-center">
                      Sign In
                    </Button>
                  </Link>
                  <Link
                    href="/register"
                    onClick={() => setMobileMenuOpen(false)}
                    className="w-full"
                  >
                    <Button className="w-full justify-center bg-emerald-600 hover:bg-emerald-700 text-white">
                      Create Customer Account
                    </Button>
                  </Link>
                  <Link
                    href="/register/retailer"
                    onClick={() => setMobileMenuOpen(false)}
                    className="w-full"
                  >
                    <Button variant="ghost" className="w-full justify-center text-xs text-muted-foreground hover:text-emerald-600">
                      Become a Partner Retailer (Sell on BASKET)
                    </Button>
                  </Link>
                </div>
              )}
            </div>
          </nav>
        </div>
      )}
    </header>
  );
}

