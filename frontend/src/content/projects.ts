/**
 * Showcase projects for the home "Projects" section carousel. Swap `image` for
 * a real landing-page screenshot (drop it in `public/projects/`) and update the
 * copy / `url` as the portfolio grows.
 */

export interface ProjectKeyInfo {
  label: string;
  value: string;
}

export interface Project {
  id: string;
  name: string;
  /** Short label used in the one-row tabs (keep it ~2 words so the row fits). */
  short: string;
  /** One-line description shown under the title. */
  tagline: string;
  /** Path under /public — a landing-page screenshot or representative image. */
  image: string;
  /** Optional live URL (rendered as the top-right "open" icon). */
  url?: string;
  /** Key facts only — kept short so the panel stays scannable. */
  keyInfo: ProjectKeyInfo[];
}

export const projects: Project[] = [
  {
    id: "akris",
    name: "Akris Website",
    short: "Akris",
    tagline:
      "A presentation site with a custom scraper that pulls official statistics into a sleek, modern dashboard.",
    image: "/projects/akris-home.png",
    url: "https://www.nsttvakris.nl/",
    keyInfo: [
      { label: "Type", value: "Sports club website" },
      { label: "Stack", value: "Next.js · Web scraper" },
      { label: "Focus", value: "Live stats dashboard" },
    ],
  },
  {
    id: "pluxbox",
    name: "Pluxbox Website",
    short: "Pluxbox",
    tagline: "A crisp product site for a software company",
    image: "/projects/pluxbox-home.png",
    url: "https://www.pluxbox.com",
    keyInfo: [
      { label: "Type", value: "SaaS / product website" },
      { label: "Stack", value: "Next.js · Tailwind · Motion" },
      { label: "Focus", value: "Clarity, conversion" },
    ],
  },
  {
    id: "roman-mariana",
    name: "Roman Mariana - Business Website",
    short: "Roman Mariana",
    tagline:
      "A polished business site with custom email integrations that automate customer-business communication.",
    image: "/projects/roman-mariana-home.png",
    url: "https://bejmarianaroman.ro/",
    keyInfo: [
      { label: "Type", value: "Business website" },
      { label: "Stack", value: "Next.js · Email automation" },
      { label: "Focus", value: "Email automation, lead gen" },
    ],
  },
];
