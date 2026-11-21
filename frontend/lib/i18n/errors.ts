import { ApiClientError } from "@/lib/api/client";

/**
 * Turn an API error into a translated message. Known backend error codes map
 * to `errors.<CODE>` keys; anything else falls back to the server message (or
 * a generic translated message for network failures).
 */
export function errorMessage(
  err: unknown,
  t: (k: string, v?: Record<string, string | number>) => string,
): string {
  if (err instanceof ApiClientError) {
    const key = `errors.${err.code}`;
    const translated = t(key);
    if (translated !== key) return translated;
    if (err.status === 0) return t("errors.NETWORK");
    return err.message || t("common.error");
  }
  if (err instanceof Error && /fetch|network/i.test(err.message)) return t("errors.NETWORK");
  return t("common.error");
}
