import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { PageTransition } from "@/components/nav/PageTransition";
import { MarketingProviders } from "./providers";

/**
 * Server Component layout for marketing routes (root, log-in, about,
 * contact). Renders the static Header shell + Footer as HTML. Client
 * state (auth + loading) is mounted by <MarketingProviders>, which
 * itself is a thin "use client" boundary.
 */
export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return (
    <MarketingProviders>
      <Header />
      <main className="min-h-screen pt-14 sm:pt-16">
        <PageTransition>{children}</PageTransition>
      </main>
      <Footer />
    </MarketingProviders>
  );
}
