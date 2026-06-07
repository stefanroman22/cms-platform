import type { Metadata } from "next";
import { about } from "@/content/about";
import { AboutStory } from "@/components/about/AboutStory";
import { TeamSection } from "@/components/about/TeamSection";

export const metadata: Metadata = {
  title: "About — Roman Technologies",
  description: about.hero.lead,
};

/**
 * About page. All copy + the team live in `src/content/about.json`.
 * Sections are client islands (motion); this page just composes them.
 */
export default function AboutPage() {
  return (
    <div className="bg-black">
      <AboutStory story={about.story} values={about.values} />
      <TeamSection team={about.team} />
    </div>
  );
}
