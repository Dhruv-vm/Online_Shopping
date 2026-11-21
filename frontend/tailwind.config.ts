import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./features/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        // BASKET brand palette (official logo colours)
        brand: {
          DEFAULT: "#080808", // Basket black: primary actions, links, header/footer
          dark: "#000000",
          light: "#FFF6D9", // soft yellow tint for highlighted surfaces
          yellow: "#FDCD1E", // sampled from the official logo
          "yellow-dark": "#E8B800",
          green: "#009B70", // existing Basket brand green (success, positive)
          "green-logo": "#007E1C", // logo wheel green
        },
        ink: "#080808",
        charcoal: "#1A1A1A",
        surface: "#FAF8F4", // warm off-white page background (reference)
        cream: "#F3EFE7",
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
        card: "1.125rem",
        hero: "1.75rem",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(8,8,8,0.04), 0 10px 28px -14px rgba(8,8,8,0.16)",
        "card-hover": "0 2px 4px rgba(8,8,8,0.05), 0 18px 40px -16px rgba(8,8,8,0.24)",
        nav: "0 12px 32px -16px rgba(8,8,8,0.45)",
      },
      transitionTimingFunction: {
        out: "cubic-bezier(0.22, 1, 0.36, 1)",
      },
      transitionDuration: {
        fast: "150ms",
        base: "220ms",
        slow: "420ms",
      },
      keyframes: {
        "fade-up": { from: { opacity: "0", transform: "translateY(14px)" }, to: { opacity: "1", transform: "none" } },
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        "scale-in": { from: { opacity: "0", transform: "scale(0.96)" }, to: { opacity: "1", transform: "none" } },
        "cart-bump": { "0%,100%": { transform: "scale(1)" }, "30%": { transform: "scale(1.22) rotate(-8deg)" }, "60%": { transform: "scale(0.94)" } },
        "badge-pop": { "0%": { transform: "scale(0.4)" }, "60%": { transform: "scale(1.18)" }, "100%": { transform: "scale(1)" } },
        "heart-pop": { "0%": { transform: "scale(1)" }, "35%": { transform: "scale(1.3)" }, "70%": { transform: "scale(0.92)" }, "100%": { transform: "scale(1)" } },
      },
      animation: {
        "fade-up": "fade-up 480ms cubic-bezier(0.22,1,0.36,1) both",
        "fade-in": "fade-in 320ms cubic-bezier(0.22,1,0.36,1) both",
        "scale-in": "scale-in 420ms cubic-bezier(0.22,1,0.36,1) both",
        "cart-bump": "cart-bump 520ms cubic-bezier(0.22,1,0.36,1)",
        "badge-pop": "badge-pop 360ms cubic-bezier(0.22,1,0.36,1)",
        "heart-pop": "heart-pop 380ms cubic-bezier(0.22,1,0.36,1)",
      },
    },
  },
  plugins: [],
};

export default config;
