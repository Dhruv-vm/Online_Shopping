"use client";

/**
 * Application-wide internationalisation (Bharat Multilingual).
 *
 * - 12 languages (lib/i18n/languages.ts); dictionaries in locales/<code>.json.
 * - The choice is stored in a cookie (read server-side by the root layout, so
 *   the first render is already translated and <html lang/dir> is correct),
 *   in localStorage, and — for signed-in users — on the account
 *   (users.preferred_language), so it survives refreshes and new logins.
 * - Missing keys fall back to English. Brand and model names are never
 *   translated (they come from the catalogue untouched).
 * - Switching language is purely client-side: cart and form state are kept.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { setActiveLanguage, translate } from "./dictionaries.ts";
import { formatDate, formatMoney, formatNumber } from "./format.ts";
import {
  DEFAULT_LANGUAGE,
  LANG_COOKIE,
  LANGUAGES,
  isLanguageCode,
  languageMeta,
  type LanguageCode,
} from "./languages.ts";

export { LANGUAGES, type LanguageCode } from "./languages.ts";
export { translate } from "./dictionaries.ts";

const STORAGE_KEY = "basket.lang";

interface I18nValue {
  lang: LanguageCode;
  dir: "ltr" | "rtl";
  setLang: (l: LanguageCode, opts?: { persistToAccount?: boolean }) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
  money: (paise: number, opts?: { decimals?: boolean }) => string;
  number: (n: number) => string;
  date: (v: string | number | Date, style?: "date" | "datetime") => string;
}

const I18nContext = createContext<I18nValue | null>(null);

function writeCookie(lang: LanguageCode) {
  try {
    document.cookie = `${LANG_COOKIE}=${lang}; path=/; max-age=31536000; samesite=lax`;
  } catch {
    /* ignore */
  }
}

export function I18nProvider({
  children,
  initialLang = DEFAULT_LANGUAGE,
}: {
  children: React.ReactNode;
  initialLang?: LanguageCode;
}) {
  const [lang, setLangState] = useState<LanguageCode>(initialLang);

  useEffect(() => {
    // localStorage may hold a choice made before the cookie existed.
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      if (isLanguageCode(saved) && saved !== initialLang) {
        setLangState(saved);
        writeCookie(saved);
      }
    } catch {
      /* storage unavailable */
    }
  }, [initialLang]);

  setActiveLanguage(lang);

  useEffect(() => {
    const meta = languageMeta(lang);
    document.documentElement.lang = lang;
    document.documentElement.dir = meta.dir;
  }, [lang]);

  const setLang = useCallback((l: LanguageCode, opts?: { persistToAccount?: boolean }) => {
    setLangState(l);
    writeCookie(l);
    try {
      window.localStorage.setItem(STORAGE_KEY, l);
    } catch {
      /* ignore */
    }
    if (opts?.persistToAccount !== false) {
      // Saved on the account for signed-in users; guests get a harmless 401.
      import("@/lib/api/phase3").then((m) => m.setLanguagePreference(l)).catch(() => undefined);
    }
  }, []);

  const value = useMemo<I18nValue>(
    () => ({
      lang,
      dir: languageMeta(lang).dir,
      setLang,
      t: (k, v) => translate(lang, k, v),
      money: (p, o) => formatMoney(p, lang, o),
      number: (n) => formatNumber(n, lang),
      date: (v, s) => formatDate(v, lang, s),
    }),
    [lang, setLang],
  );
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const ctx = useContext(I18nContext);
  if (ctx) return ctx;
  const lang = DEFAULT_LANGUAGE;
  return {
    lang,
    dir: "ltr",
    setLang: () => undefined,
    t: (k, v) => translate(lang, k, v),
    money: (p, o) => formatMoney(p, lang, o),
    number: (n) => formatNumber(n, lang),
    date: (v, s) => formatDate(v, lang, s),
  };
}

export function LanguageSwitcher({ compact = false }: { compact?: boolean }) {
  const { lang, setLang, t } = useI18n();
  return (
    <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
      {!compact && <span className="hidden xl:inline">{t("common.language")}</span>}
      <select
        aria-label={t("common.language")}
        value={lang}
        onChange={(e) => setLang(e.target.value as LanguageCode)}
        className="h-8 rounded-md border border-border bg-background px-2 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-brand/40"
      >
        {LANGUAGES.map((l) => (
          <option key={l.code} value={l.code}>
            {l.native}
          </option>
        ))}
      </select>
    </label>
  );
}
