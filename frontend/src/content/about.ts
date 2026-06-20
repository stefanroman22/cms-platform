/**
 * About-page content. Edit everything in `about.json` — this module just adds
 * types so the components stay safe. The team's role and description copy lives
 * in `messages/*.json` under `about.team.members.<id>`; this file holds the
 * data-only member records (name, image, email, LinkedIn). To swap a photo,
 * drop a file into `public/team/` and point that member's `image` at it
 * (e.g. "/team/stefan-roman.jpg").
 */
import data from "./about.json";

export interface TeamMember {
  /** Stable id; matches the key under `about.team.members` in the messages. */
  id: string;
  name: string;
  /** Path under /public, e.g. "/team/stefan-roman.svg". */
  image: string;
  email: string;
  linkedin: string;
}

export interface AboutContent {
  members: TeamMember[];
}

export const about = data as AboutContent;
