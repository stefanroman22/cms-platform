import type { NextConfig } from "next";

/**
 * Browser-side security headers applied to every Next.js response.
 *
 * Why each header is here:
 * - HSTS: forces HTTPS for two years on roman-technologies.dev. Vercel does
 *   NOT add this automatically for serverless function responses on the
 *   `*.vercel.app` subdomain — we set it explicitly.
 * - X-Content-Type-Options: stops MIME sniffing (CWE-693).
 * - X-Frame-Options + frame-ancestors 'none': blocks click-jacking against
 *   admin actions (publish, delete, transfer). The dashboard never
 *   intentionally embeds itself.
 * - Referrer-Policy: strips path/query when navigating to other origins.
 * - Permissions-Policy: revokes powerful APIs we never use.
 * - Content-Security-Policy: defense-in-depth against any future XSS sink.
 *   Allows `'unsafe-inline'` for styles+scripts because Next.js inlines
 *   hydration scripts and Tailwind classes; tightening this requires nonce
 *   plumbing which is a separate piece of work.
 *
 * The CSP is not the strictest possible (e.g. no `'strict-dynamic'`) but
 * it closes the click-jacking and base-uri / form-action holes which were
 * the spec's main concern (FE-001 / INFRA-002).
 */
const securityHeaders = [
  {
    key: "Strict-Transport-Security",
    value: "max-age=63072000; includeSubDomains; preload",
  },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), interest-cohort=()",
  },
  {
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
      "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
      "font-src 'self' https://fonts.gstatic.com",
      "img-src 'self' data: https:",
      // Embedded video providers used by the CMS VideoEditor only.
      "frame-src https://www.youtube.com https://player.vimeo.com",
      // Same-origin fetch only — covers the /api/[...path] proxy and the
      // Resend-rendered images that travel via direct https:.
      "connect-src 'self' https:",
      "frame-ancestors 'none'",
      "base-uri 'self'",
      "form-action 'self'",
    ].join("; "),
  },
];

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        // Apply to every path, including /api/* (server-side proxy) and
        // static assets. Vercel still serves PNGs / SVGs without these
        // headers when the request hits the CDN edge before Next.js;
        // that's acceptable for public assets.
        source: "/:path*",
        headers: securityHeaders,
      },
    ];
  },
};

export default nextConfig;
