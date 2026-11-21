import { languageMeta, type LanguageCode } from "./languages.ts";

/** Indian-rupee amount from paise, formatted for the active language. */
export function formatMoney(paise: number, lang: LanguageCode, opts: { decimals?: boolean } = {}): string {
  const rupees = (paise || 0) / 100;
  const decimals = opts.decimals ?? !Number.isInteger(rupees);
  try {
    return new Intl.NumberFormat(languageMeta(lang).intl, {
      style: "currency",
      currency: "INR",
      minimumFractionDigits: decimals ? 2 : 0,
      maximumFractionDigits: decimals ? 2 : 0,
    }).format(rupees);
  } catch {
    return `₹${rupees.toLocaleString("en-IN")}`;
  }
}

export function formatNumber(n: number, lang: LanguageCode): string {
  try {
    return new Intl.NumberFormat(languageMeta(lang).intl).format(n);
  } catch {
    return String(n);
  }
}

export function formatDate(
  value: string | number | Date,
  lang: LanguageCode,
  style: "date" | "datetime" = "date",
): string {
  const d = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  try {
    return new Intl.DateTimeFormat(languageMeta(lang).intl, {
      day: "numeric",
      month: "short",
      year: "numeric",
      ...(style === "datetime" ? { hour: "numeric", minute: "2-digit" } : {}),
    }).format(d);
  } catch {
    return d.toLocaleDateString("en-IN");
  }
}
