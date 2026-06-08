import { LenisProvider } from "@/components/providers/LenisProvider";
import { HeroSection } from "@/components/hero/HeroSection";
import { LaptopShowcase } from "@/components/hero/LaptopShowcase";
import { ContactSection } from "@/components/contact/ContactSection";
import { WorkSection } from "@/components/work/WorkSection";
import { PricingSection } from "@/components/pricing/PricingSection";

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
