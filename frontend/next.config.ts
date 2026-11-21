import type { NextConfig } from "next";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Shared two-laptop demo: the browser only talks to this Next.js server, which
// proxies the API and media to a backend bound to 127.0.0.1 (one URL for LAN or
// a tunnel, no cross-origin cookies, nothing else exposed). Inert unless
// BASKET_API_PROXY_TARGET is set.
const apiProxy = process.env.BASKET_API_PROXY_TARGET?.replace(/\/+$/, "");

const nextConfig: NextConfig = {
  outputFileTracingRoot: __dirname,
  reactStrictMode: true,
  // A separate build directory lets the shared demo build run next to a dev server.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "images.unsplash.com",
      },
    ],
  },
  ...(apiProxy
    ? {
        // Do not buffer proxied Server-Sent Events.
        compress: false,
        async rewrites() {
          return [
            { source: "/api/v1/:path*", destination: `${apiProxy}/api/v1/:path*` },
            { source: "/media/:path*", destination: `${apiProxy}/media/:path*` },
          ];
        },
      }
    : {}),
};

export default nextConfig;
