import type { Metadata, Viewport } from "next";
import { Montserrat } from "next/font/google";
import { cookies } from "next/headers";
import { Header } from "@/components/shared/header";
import { Footer } from "@/components/shared/footer";
import { AuthProvider } from "@/lib/auth/auth-context";
import { CartProvider } from "@/lib/cart/cart-context";
import { CompareProvider } from "@/lib/compare/compare-context";
import { WishlistProvider } from "@/lib/wishlist/wishlist-context";
import { I18nProvider } from "@/lib/i18n/i18n-context";
import { LanguageAccountSync } from "@/lib/i18n/account-sync";
import { DEFAULT_LANGUAGE, LANG_COOKIE, isLanguageCode, languageMeta } from "@/lib/i18n/languages";
import { InitialLoader, LOADING_CLASS_SCRIPT } from "@/components/loader/initial-loader";
import { LoaderReady } from "@/components/loader/loader-ready";
import { RouteLoader } from "@/components/loader/route-loader";
import "@/components/loader/basket-loader.css";
import "./globals.css";

// Montserrat: the Hack UI loader's typeface and a close match to the logo wordmark.
const sans = Montserrat({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  display: "swap",
  variable: "--font-sans",
});

export const viewport: Viewport = { themeColor: "#080808" };

export const metadata: Metadata = {
  title: "Basket — Everything. In one Basket.",
  description:
    "Shop electronics, groceries, fashion and home essentials from verified local stores across India.",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const cookieLang = (await cookies()).get(LANG_COOKIE)?.value;
  const lang = isLanguageCode(cookieLang) ? cookieLang : DEFAULT_LANGUAGE;
  const { dir } = languageMeta(lang);
  return (
    <html lang={lang} dir={dir} className={sans.variable} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: LOADING_CLASS_SCRIPT }} />
        <link rel="preload" as="image" href="/brand/basket-logo.webp" type="image/webp" />
        <link rel="preload" as="image" href="/brand/cart-body.webp" type="image/webp" />
        <link rel="preload" as="image" href="/brand/cart-wheels.webp" type="image/webp" />
      </head>
      <body className="flex min-h-screen flex-col bg-surface font-sans text-ink antialiased">
        <InitialLoader />
        <I18nProvider initialLang={lang}>
          <AuthProvider>
            <LanguageAccountSync />
            <CartProvider>
              <CompareProvider>
               <WishlistProvider>
                <LoaderReady />
                <RouteLoader />
                <Header />
                <main className="flex-1">{children}</main>
                <Footer />
               </WishlistProvider>
              </CompareProvider>
            </CartProvider>
          </AuthProvider>
        </I18nProvider>
      </body>
    </html>
  );
}
