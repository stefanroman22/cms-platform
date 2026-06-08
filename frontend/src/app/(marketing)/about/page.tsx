import type { Metadata } from "next";
import { about } from "@/content/about";
import { AboutStory } from "@/components/about/AboutStory";
import { WhatWeDo } from "@/components/work/WhatWeDo";

export const metadata: Metadata = {
  title: "About — Roman Technologies",
  description: about.hero.lead,
};

/**
 * About page. Copy lives in `src/content/about.json`. The page composes the
 * "Who we are" story with the full-width "What do we do" block (shared with the
 * home page). The team now lives on `/team`.
 */
export default function AboutPage() {
  return (
    <div className="bg-black">
      <AboutStory story={about.story} />
      <WhatWeDo layout="full" />
    </div>
  );
}
