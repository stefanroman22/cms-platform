import type { Metadata } from "next";
import { LenisProvider } from "@/components/providers/LenisProvider";
import { HeroSection } from "@/components/hero/HeroSection";
import { LaptopShowcase } from "@/components/hero/LaptopShowcase";
import { ContactSection } from "@/components/contact/ContactSection";
import { WorkSection } from "@/components/work/WorkSection";
import { PricingSection } from "@/components/pricing/PricingSection";
import { buildAlternates } from "@/i18n/alternates";
import type { Locale } from "@/lib/locale";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: Locale }>;
}): Promise<Metadata> {
  const { locale } = await params;
  return { alternates: buildAlternates("/", locale) };
}

export default function Home() {
  return (
    <LenisProvider>
      <HeroSection />
      <LaptopShowcase />
      <ContactSection />
      <WorkSection />
      <PricingSection />
    </LenisProvider>
  );
}
