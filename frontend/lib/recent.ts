/** Recently viewed products, kept on this device only (max 12). */
export interface RecentProduct {
  slug: string;
  name: string;
  brand: string;
  image: string | null;
  price_paise: number;
}
const KEY = "basket.recentlyViewed";

export function getRecent(): RecentProduct[] {
  try {
    const raw = window.localStorage.getItem(KEY);
    const list = raw ? (JSON.parse(raw) as RecentProduct[]) : [];
    return Array.isArray(list) ? list.filter((p) => p && typeof p.slug === "string") : [];
  } catch {
    return [];
  }
}

export function recordView(p: RecentProduct): void {
  try {
    const next = [p, ...getRecent().filter((x) => x.slug !== p.slug)].slice(0, 12);
    window.localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    /* ignore */
  }
}
