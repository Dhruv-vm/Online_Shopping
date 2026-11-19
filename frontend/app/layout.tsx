import type { Metadata } from "next";
import { Header } from "@/components/shared/header";
import { Footer } from "@/components/shared/footer";
import { AuthProvider } from "@/lib/auth/auth-context";
import { CartProvider } from "@/lib/cart/cart-context";
import { CompareProvider } from "@/lib/compare/compare-context";
import "./globals.css";

export const metadata: Metadata = {
  title: "BASKET — Foundation Platform",
  description: "BASKET multi-category online retail platform - Phase 0 Engineering Foundation",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="flex min-h-screen flex-col font-sans antialiased">
        <AuthProvider>
          <CartProvider>
            <CompareProvider>
              <Header />
              <main className="flex-1">{children}</main>
              <Footer />
            </CompareProvider>
          </CartProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
