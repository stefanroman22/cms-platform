import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/Providers";
import { SiteShell } from "@/components/SiteShell";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Roman Technologies",
  description: "Premium software solutions for modern businesses.",
};

/**
 * Theme boot script — placed RAW in <head> so the browser executes it
 * synchronously before parsing <body>. This is the only way to apply
 * `class="dark"` on <html> before first paint — `next/script` with
 * `strategy="beforeInteractive"` injects into <body>, which fires too
 * late under dev/Turbopack and produces a one-frame light flash.
 *
 * Reads `dashboard-theme` from localStorage; defaults to "dark" if
 * missing or invalid. Sets BOTH:
 *   • `class="dark"` on <html> — picked up by Tailwind via the
 *     `@custom-variant dark` rule in globals.css.
 *   • `data-theme="dark|light"` — read by `context/theme.tsx` on
 *     mount so React state agrees with what's already on the DOM.
 *
 * Trade-off: React 19 logs a dev-only "scripts inside React components
 * are never executed when rendering on the client" warning. The script
 * has already run during initial HTML parse — that's all we need; the
 * warning is informational only and never appears in production builds.
 */
const themeBootScript = `(function(){try{var t=localStorage.getItem('dashboard-theme');if(t!=='light'&&t!=='dark')t='dark';document.documentElement.dataset.theme=t;document.documentElement.classList.toggle('dark',t==='dark');}catch(e){document.documentElement.dataset.theme='dark';document.documentElement.classList.add('dark');}})();`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* `suppressHydrationWarning`: some browser extensions
            (e.g. "Popups Notification" with id lgblnfidahcdcjddiepkckcfdhpknnjh)
            rewrite this `<script>` between the SSR HTML arriving and
            React hydrating — they replace the inner content with a
            `src="chrome-extension://..."` reference. Without
            suppression, React 19 logs a hydration mismatch even
            though our rendered tree is unchanged. The script has
            already run during initial parse, so the rewrite is
            cosmetic; suppress the warning to keep the dev console
            clean. */}
        <script
          suppressHydrationWarning
          dangerouslySetInnerHTML={{ __html: themeBootScript }}
        />
      </head>
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <Providers>
          <SiteShell>{children}</SiteShell>
        </Providers>
      </body>
    </html>
  );
}
