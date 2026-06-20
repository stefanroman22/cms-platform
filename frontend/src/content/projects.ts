/**
 * Showcase projects for the home "Projects" section carousel. Swap `image` for
 * a real landing-page screenshot (drop it in `public/projects/`) and update the
 * copy / `url` as the portfolio grows.
 */

export interface Project {
  id: string;
  name: string;
  /** Short label used in the one-row tabs (keep it ~2 words so the row fits). */
  short: string;
  /** Path under /public — a landing-page screenshot or representative image. */
  image: string;
  /** Optional live URL (rendered as the top-right "open" icon). */
  url?: string;
}

export const projects: Project[] = [
  {
    id: "akris",
    name: "Akris Website",
    short: "Akris",
    image: "/projects/akris-home.png",
    url: "https://www.nsttvakris.nl/",
  },
  {
    id: "pluxbox",
    name: "Pluxbox Website",
    short: "Pluxbox",
    image: "/projects/pluxbox-home.png",
    url: "https://www.pluxbox.com",
  },
  {
    id: "roman-mariana",
    name: "Roman Mariana - Business Website",
    short: "Roman Mariana",
    image: "/projects/roman-mariana-home.png",
    url: "https://bejmarianaroman.ro/",
  },
];
