"use client";

import { useEffect, useRef } from "react";
import { useAuth } from "@/lib/auth/auth-context";
import { isLanguageCode } from "./languages.ts";
import { useI18n } from "./i18n-context";

/**
 * Keeps the interface language and the account preference in step:
 * on sign-in the account's saved language is applied; if the account still has
 * the default (English) but the visitor chose another language before signing
 * in, that choice is saved to the account instead.
 */
export function LanguageAccountSync() {
  const { user } = useAuth();
  const { lang, setLang } = useI18n();
  const lastUserId = useRef<string | null>(null);

  useEffect(() => {
    const id = user?.id ?? null;
    if (id === lastUserId.current) return;
    lastUserId.current = id;
    if (!user) return;
    const saved = user.preferred_language;
    if (isLanguageCode(saved) && saved !== "en" && saved !== lang) {
      setLang(saved, { persistToAccount: false });
    } else if ((!saved || saved === "en") && lang !== "en") {
      setLang(lang); // save the guest's choice on the account
    }
  }, [user, lang, setLang]);

  return null;
}
