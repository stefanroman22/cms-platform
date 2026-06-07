import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
  display: "swap",
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
 * synchronously before parsing <body>. Reads `dashboard-theme` from
 * localStorage; defaults to "dark". Sets `class="dark"` on <html> and
 * `data-theme="dark|light"` for `context/theme.tsx` to pick up on mount.
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
        <script suppressHydrationWarning dangerouslySetInnerHTML={{ __html: themeBootScript }} />
      </head>
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>{children}</body>
    </html>
  );
}
