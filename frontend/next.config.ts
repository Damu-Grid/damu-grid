import type { NextConfig } from "next";

// Where /api/backend/* is relayed. The browser only talks to this app, so the
// backend needs no CORS headers.
const BACKEND_URL = (process.env.BACKEND_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

const nextConfig: NextConfig = {
  // Separate build folders let tests and CI builds run while `pnpm dev` is up;
  // sharing `.next` makes the running dev server return 500s.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  async rewrites() {
    return [{ source: "/api/backend/:path*", destination: `${BACKEND_URL}/:path*` }];
  },
};

export default nextConfig;
