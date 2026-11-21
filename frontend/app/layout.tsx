import type { Metadata } from "next";
import { cookies } from "next/headers";
import { Header } from "@/components/shared/header";
import { Footer } from "@/components/shared/footer";
import { AuthProvider } from "@/lib/auth/auth-context";
import { CartProvider } from "@/lib/cart/cart-context";
import { CompareProvider } from "@/lib/compare/compare-context";
import { I18nProvider } from "@/lib/i18n/i18n-context";
import { LanguageAccountSync } from "@/lib/i18n/account-sync";
import { DEFAULT_LANGUAGE, LANG_COOKIE, isLanguageCode, languageMeta } from "@/lib/i18n/languages";
import "./globals.css";

export const metadata: Metadata = {
  title: "BASKET — India's multi-store marketplace",
  description:
    "Shop electronics, groceries, fashion and home essentials from verified local stores across India.",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const cookieLang = (await cookies()).get(LANG_COOKIE)?.value;
  const lang = isLanguageCode(cookieLang) ? cookieLang : DEFAULT_LANGUAGE;
  const { dir } = languageMeta(lang);
  return (
    <html lang={lang} dir={dir}>
      <body className="flex min-h-screen flex-col bg-surface font-sans text-charcoal antialiased">
        <I18nProvider initialLang={lang}>
          <AuthProvider>
            <LanguageAccountSync />
            <CartProvider>
              <CompareProvider>
                <Header />
                <main className="flex-1">{children}</main>
                <Footer />
              </CompareProvider>
            </CartProvider>
          </AuthProvider>
        </I18nProvider>
      </body>
    </html>
  );
}
