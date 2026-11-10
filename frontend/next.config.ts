import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Separate build folders let tests and CI builds run while `pnpm dev` is up;
  // sharing `.next` makes the running dev server return 500s.
  distDir: process.env.NEXT_DIST_DIR || ".next",
};

export default nextConfig;
