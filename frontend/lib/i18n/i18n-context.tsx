"use client";

/**
 * Bharat Multilingual UI foundation (Phase 3H).
 * Dictionaries live in frontend/locales/{lang}.json (spec layout). Implemented
 * without next-intl to avoid a new dependency and a [locale] route restructure
 * before the redesign; the dictionary format is next-intl compatible.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import en from "@/locales/en.json";
import hi from "@/locales/hi.json";
import ta from "@/locales/ta.json";
import te from "@/locales/te.json";
import kn from "@/locales/kn.json";
import bn from "@/locales/bn.json";
import mr from "@/locales/mr.json";
import gu from "@/locales/gu.json";

export const LANGUAGES = [
  { code: "en", native: "English" },
  { code: "hi", native: "हिन्दी" },
  { code: "ta", native: "தமிழ்" },
  { code: "te", native: "తెలుగు" },
  { code: "kn", native: "ಕನ್ನಡ" },
  { code: "bn", native: "বাংলা" },
  { code: "mr", native: "मराठी" },
  { code: "gu", native: "ગુજરાતી" },
] as const;
export type LanguageCode = (typeof LANGUAGES)[number]["code"];
type Dict = Record<string, string>;
const DICTS: Record<LanguageCode, Dict> = { en, hi, ta, te, kn, bn, mr, gu };
const STORAGE_KEY = "basket.lang";

interface I18nValue {
  lang: LanguageCode;
  setLang: (l: LanguageCode) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
}

const I18nContext = createContext<I18nValue | null>(null);

export function translate(lang: LanguageCode, key: string, vars?: Record<string, string | number>): string {
  const raw = DICTS[lang]?.[key] ?? DICTS.en[key] ?? key;
  return vars ? raw.replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? `{${k}}`)) : raw;
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<LanguageCode>("en");

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY) as LanguageCode | null;
      if (saved && saved in DICTS) setLangState(saved);
    } catch {
      /* storage unavailable: keep default */
    }
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = useCallback((l: LanguageCode) => {
    setLangState(l);
    try {
      window.localStorage.setItem(STORAGE_KEY, l);
    } catch {
      /* ignore */
    }
    // Persist for signed-in users; ignore failures for guests.
    import("@/lib/api/phase3").then((m) => m.setLanguagePreference(l)).catch(() => undefined);
  }, []);

  const value = useMemo<I18nValue>(() => ({ lang, setLang, t: (k, v) => translate(lang, k, v) }), [lang, setLang]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const ctx = useContext(I18nContext);
  if (!ctx) return { lang: "en", setLang: () => undefined, t: (k, v) => translate("en", k, v) };
  return ctx;
}

export function LanguageSwitcher() {
  const { lang, setLang, t } = useI18n();
  return (
    <label className="flex items-center gap-1 text-xs text-gray-600">
      <span className="sr-only">{t("common.language")}</span>
      <select
        aria-label={t("common.language")}
        value={lang}
        onChange={(e) => setLang(e.target.value as LanguageCode)}
        className="rounded border border-gray-200 bg-white px-1.5 py-1 text-xs"
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
