/**
 * Role-based navigation helpers. The role always comes from the backend
 * (login response / /users/me); the browser never chooses it.
 */
export type Role = "customer" | "retailer" | "admin";

export function homeForRole(role: string | null | undefined): string {
  if (role === "admin") return "/admin";
  if (role === "retailer") return "/retailer";
  return "/";
}

const CUSTOMER_ONLY = ["/cart", "/checkout", "/orders", "/account"];

/**
 * Where to send a user after sign-in. A requested `redirect` is honoured only
 * if it is a same-site path the role may actually open; otherwise the role's
 * home is used (so a retailer is never dropped into customer checkout).
 */
export function postLoginDestination(role: string | null | undefined, requested?: string | null): string {
  const home = homeForRole(role);
  if (!requested || !requested.startsWith("/") || requested.startsWith("//")) return home;
  if (requested.startsWith("/admin")) return role === "admin" ? requested : home;
  if (requested.startsWith("/retailer") && !requested.startsWith("/retailers")) {
    return role === "retailer" ? requested : home;
  }
  if (role !== "customer" && CUSTOMER_ONLY.some((p) => requested === p || requested.startsWith(`${p}/`))) {
    return home;
  }
  if (requested === "/login" || requested.startsWith("/register")) return home;
  return requested;
}

/** Customers and guests shop; retailer/admin sessions never hold a checkout. */
export function canShop(role: string | null | undefined): boolean {
  return !role || role === "customer";
}
