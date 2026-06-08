/**
 * About-page content. Edit everything in `about.json` — this module just adds
 * types so the components stay safe. To change copy, the team, emails, LinkedIn
 * links or which image a person uses, open `about.json`. To swap a photo, drop
 * a file into `public/team/` and point that member's `image` at it
 * (e.g. "/team/stefan-roman.jpg").
 */
import data from "./about.json";

export interface TeamMember {
  name: string;
  role: string;
  /** Shown as the overlay that fades in when hovering the photo. */
  description: string;
  /** Path under /public, e.g. "/team/stefan-roman.svg". */
  image: string;
  email: string;
  linkedin: string;
}

export interface AboutContent {
  hero: { eyebrow: string; title: string; lead: string };
  story: { heading: string; paragraphs: string[] };
  team: { heading: string; subheading: string; members: TeamMember[] };
}

export const about = data as AboutContent;
