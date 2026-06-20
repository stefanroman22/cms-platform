import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { buildAlternates } from "@/i18n/alternates";
import type { Locale } from "@/lib/locale";
import { AboutStory } from "@/components/about/AboutStory";
import { WhatWeDo } from "@/components/work/WhatWeDo";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: Locale }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const tPage = await getTranslations({ locale, namespace: "aboutPage" });
  const tAbout = await getTranslations({ locale, namespace: "about" });
  return {
    title: tPage("metaTitle"),
    description: tAbout("hero.lead"),
    alternates: buildAlternates("/about", locale),
  };
}

/**
 * About page. Copy lives in `messages/*.json` under the `about` namespace. The
 * page composes the "Who we are" story with the full-width "What do we do"
 * block (shared with the home page). The team now lives on `/team`.
 */
export default function AboutPage() {
  return (
    <div className="bg-black">
      <AboutStory />
      <WhatWeDo layout="full" />
    </div>
  );
}
