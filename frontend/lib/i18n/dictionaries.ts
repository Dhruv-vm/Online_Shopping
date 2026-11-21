import en from "../../locales/en.json" with { type: "json" };
import hi from "../../locales/hi.json" with { type: "json" };
import kn from "../../locales/kn.json" with { type: "json" };
import ta from "../../locales/ta.json" with { type: "json" };
import te from "../../locales/te.json" with { type: "json" };
import ml from "../../locales/ml.json" with { type: "json" };
import bn from "../../locales/bn.json" with { type: "json" };
import mr from "../../locales/mr.json" with { type: "json" };
import gu from "../../locales/gu.json" with { type: "json" };
import pa from "../../locales/pa.json" with { type: "json" };
import or from "../../locales/or.json" with { type: "json" };
import ur from "../../locales/ur.json" with { type: "json" };
import type { LanguageCode } from "./languages.ts";

export type Dictionary = Record<string, string>;

export const DICTIONARIES: Record<LanguageCode, Dictionary> = {
  en, hi, kn, ta, te, ml, bn, mr, gu, pa, or, ur,
};

/** Translate a key; falls back to English, then to the key itself. */
export function translate(
  lang: LanguageCode,
  key: string,
  vars?: Record<string, string | number>,
): string {
  const raw = DICTIONARIES[lang]?.[key] ?? DICTIONARIES.en[key] ?? key;
  return vars ? raw.replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? `{${k}}`)) : raw;
}

/** Keys present in English but missing from a language (for tests/reports). */
export function missingKeys(lang: LanguageCode): string[] {
  const dict = DICTIONARIES[lang] ?? {};
  return Object.keys(DICTIONARIES.en).filter((k) => !(k in dict));
}

// The active language, mirrored by I18nProvider, for code that runs outside
// React render (e.g. error helpers in catch blocks).
let activeLanguage: LanguageCode = "en";
export function setActiveLanguage(lang: LanguageCode): void {
  activeLanguage = lang;
}
export function tActive(key: string, vars?: Record<string, string | number>): string {
  return translate(activeLanguage, key, vars);
}
