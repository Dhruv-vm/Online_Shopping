/**
 * Supported interface languages. Add a language by (1) adding an entry here and
 * (2) adding locales/<code>.json — missing keys fall back to English.
 */
export const LANGUAGES = [
  { code: "en", native: "English", english: "English", intl: "en-IN", dir: "ltr" },
  { code: "hi", native: "हिन्दी", english: "Hindi", intl: "hi-IN", dir: "ltr" },
  { code: "kn", native: "ಕನ್ನಡ", english: "Kannada", intl: "kn-IN", dir: "ltr" },
  { code: "ta", native: "தமிழ்", english: "Tamil", intl: "ta-IN", dir: "ltr" },
  { code: "te", native: "తెలుగు", english: "Telugu", intl: "te-IN", dir: "ltr" },
  { code: "ml", native: "മലയാളം", english: "Malayalam", intl: "ml-IN", dir: "ltr" },
  { code: "bn", native: "বাংলা", english: "Bengali", intl: "bn-IN", dir: "ltr" },
  { code: "mr", native: "मराठी", english: "Marathi", intl: "mr-IN", dir: "ltr" },
  { code: "gu", native: "ગુજરાતી", english: "Gujarati", intl: "gu-IN", dir: "ltr" },
  { code: "pa", native: "ਪੰਜਾਬੀ", english: "Punjabi", intl: "pa-IN", dir: "ltr" },
  { code: "or", native: "ଓଡ଼ିଆ", english: "Odia", intl: "or-IN", dir: "ltr" },
  { code: "ur", native: "اردو", english: "Urdu", intl: "ur-IN", dir: "rtl" },
] as const;

export type LanguageCode = (typeof LANGUAGES)[number]["code"];
export const DEFAULT_LANGUAGE: LanguageCode = "en";
/** Cookie that carries the chosen language (read server-side by the root layout). */
export const LANG_COOKIE = "basket_lang";

export function isLanguageCode(v: unknown): v is LanguageCode {
  return typeof v === "string" && LANGUAGES.some((l) => l.code === v);
}

export function languageMeta(code: LanguageCode) {
  return LANGUAGES.find((l) => l.code === code) ?? LANGUAGES[0];
}
