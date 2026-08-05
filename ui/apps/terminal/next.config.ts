import type { NextConfig } from 'next';

/**
 * Static export: `next build` emits `out/` — copy the contents into the
 * TradingBot project root and FastAPI's existing `/` handler serves it.
 * The API lives on :8000 (CORS already allows localhost); dev runs on :3000.
 */
const nextConfig: NextConfig = {
  output: 'export',
  images: { unoptimized: true },
  trailingSlash: true,
  reactStrictMode: true,
};

export default nextConfig;
