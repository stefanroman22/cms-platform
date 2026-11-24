/**
 * CMS content → next-intl messages bridge.
 *
 * The site ships local `messages/<locale>.json` as the seed/fallback (and for chrome
 * like nav/cookie/loader that isn't CMS-managed). At request time we fetch the live
 * CMS content for the active locale and DEEP-MERGE it over the local messages, so any
 * edit the owner publishes in the CMS dashboard shows on the site within the revalidate
 * window. If the CMS is unreachable or returns garbage, we silently fall back to the
 * local messages — the site never breaks.
 *
 * NEXT_PUBLIC_CMS_ENDPOINT is the locale-less base (e.g. ".../content/samir-kapsalon");
 * we append `/<locale>` for the published per-locale payload.
 */

type Json = Record<string, unknown>;

/** Map a CMS key_value service → the next-intl namespace it backs. */
const ENTRY_NS: Record<string, string> = {
  hero: "hero",
  about: "about",
  trust_band: "trust",
  services_teaser: "servicesTeaser",
  gallery_teaser: "galleryTeaser",
  reviews_section: "reviews",
  instagram: "instagram",
  location_strip: "location",
  diensten_header: "diensten",
  team_header: "team",
  gallery_header: "galerij",
  contact_content: "contact",
  booking_page_header: "booking",
  footer: "footer",
  // careers copy lives in the `team` namespace (careersEyebrow/Title/Body keys
  // match 1:1, so the CMS entries deep-merge straight over the static messages).
  team_careers: "team",
};

/** Build a partial next-intl message tree from the CMS `content` map. */
function cmsToMessages(content: Json): Json {
  const m: Json = {};
  const ns = (key: string): Json => (m[key] ??= {}) as Json;

  // key_value services → namespace (entries deep-merge over the local namespace)
  for (const [svcKey, target] of Object.entries(ENTRY_NS)) {
    const svc = content[svcKey] as Json | undefined;
    const entries = svc?.entries as Json | undefined;
    if (entries && typeof entries === "object") Object.assign(ns(target), entries);
  }

  // repeater services → nested array paths
  const items = (key: string): unknown[] | null => {
    const arr = (content[key] as Json | undefined)?.items;
    return Array.isArray(arr) ? arr : null;
  };
  const teaser = items("services_teaser_items");
  if (teaser) (ns("servicesTeaser") as Json).items = teaser;
  const notes = items("service_notes");
  if (notes) (ns("diensten") as Json).notes = notes;
  const team = items("team_members");
  if (team) (ns("team") as Json).members = team;
  const reviews = items("reviews_items");
  if (reviews) (ns("reviews") as Json).items = reviews;

  // ── Non-message site data (images, hours, contact, brand, theme) ───────────
  // These services don't map to a text namespace; they back the static constants
  // in `lib/site.ts`. We surface them under a `site` namespace that `resolveSite`
  // (lib/cms-site.ts) reads, falling back to the static constants when absent.
  const site: Json = {};
  const brand = content.general_brand_name as Json | undefined;
  if (typeof brand?.title === "string" && brand.title.trim()) site.brandName = brand.title;
  const contact = (content.contact_info as Json | undefined)?.entries;
  if (contact && typeof contact === "object") site.contact = contact;
  const hours = (content.opening_hours as Json | undefined)?.items;
  if (Array.isArray(hours) && hours.length) site.hours = hours;
  const heroUrl = (content.hero_image as Json | undefined)?.url;
  if (typeof heroUrl === "string" && heroUrl) site.heroImage = heroUrl;
  const heroAlt = (content.hero_image as Json | undefined)?.alt;
  if (typeof heroAlt === "string" && heroAlt.trim()) site.heroImageAlt = heroAlt;
  // Map card illustration: an uploaded image replaces the in-code SVG map when set.
  const map = content.location_map_image as Json | undefined;
  if (typeof map?.url === "string" && map.url) site.mapImage = map.url;
  if (typeof map?.alt === "string" && map.alt.trim()) site.mapImageAlt = map.alt;
  // Project theme (ADR-0011): raw value, validated by the kit's readTheme in resolveSite.
  const theme = content.general_theme;
  if (theme && typeof theme === "object") site.theme = theme;
  // Display options (ADR-0013): raw `<page>_page_options` services, validated by the
  // kit's readOptions in lib/page-options.ts.
  const pageOptions: Json = {};
  for (const [key, value] of Object.entries(content)) {
    if (key.endsWith("_page_options") && value && typeof value === "object") pageOptions[key] = value;
  }
  if (Object.keys(pageOptions).length) site.pageOptions = pageOptions;
  const gallery = (key: string): string[] | null => {
    const arr = (content[key] as Json | undefined)?.items;
    return Array.isArray(arr) && arr.length ? (arr as string[]) : null;
  };
  const ab = gallery("about_images");
  if (ab) site.aboutImages = ab;
  const gi = gallery("gallery_images");
  if (gi) site.galleryImages = gi;
  const gt = gallery("gallery_teaser_images");
  if (gt) site.galleryTeaserImages = gt;
  const ig = gallery("instagram_images");
  if (ig) site.instagramImages = ig;
  if (Object.keys(site).length) m.site = site;

  // service_menu is flat ({group, name, desc, meta, price}); the site renders grouped.
  const menu = items("service_menu");
  if (menu) {
    const groups: { title: string; items: Json[] }[] = [];
    const byTitle: Record<string, number> = {};
    for (const raw of menu as Json[]) {
      const title = String(raw.group ?? "");
      if (!(title in byTitle)) {
        byTitle[title] = groups.length;
        groups.push({ title, items: [] });
      }
      const { group: _group, ...rest } = raw;
      groups[byTitle[title]].items.push(rest as Json);
    }
    (ns("diensten") as Json).groups = groups;
  }

  return m;
}

/** Deep-merge `over` onto `base`: objects merge recursively, arrays + scalars from
 *  `over` win, and keys absent from `over` are preserved from `base`. */
function deepMerge<T>(base: T, over: unknown): T {
  if (over === undefined || over === null) return base;
  if (Array.isArray(over)) return over as unknown as T;
  if (typeof over === "object") {
    const out: Json = { ...(base as Json) };
    for (const [k, v] of Object.entries(over as Json)) {
      out[k] = deepMerge((base as Json)?.[k], v);
    }
    return out as unknown as T;
  }
  return over as T;
}

/** Fetch + merge CMS content over the local messages for `locale`. Never throws.
 *
 * SERVER-ONLY: this module is imported only by i18n/request.ts. The preview token
 * is read from the server-only env `CMS_PREVIEW_TOKEN` (NEVER NEXT_PUBLIC_ — it is a
 * credential and must not be inlined into the client bundle). When the token is
 * present (cms-preview deployment + localhost via .env.local) we fetch the DRAFT so
 * SAVED-but-unpublished edits show; production has no token and reads PUBLISHED.
 * Fallback chain never throws: draft 401/!ok → published → local seed. */
export async function withCmsContent(locale: string, local: Json): Promise<Json> {
  const base = (process.env.NEXT_PUBLIC_CMS_ENDPOINT || "").replace(/\/draft\/?$/, "");
  if (!base) return local;
  const token = process.env.CMS_PREVIEW_TOKEN;

  async function fetchContent(): Promise<Json | null> {
    if (token) {
      try {
        const res = await fetch(`${base}/${locale}/draft`, {
          headers: { "X-CMS-Preview-Token": token },
          cache: "no-store",
        });
        if (res.ok) {
          const p = (await res.json()) as { content?: Json };
          if (p?.content && typeof p.content === "object") return p.content;
        }
      } catch {
        /* fall through to published */
      }
    }
    try {
      const res = await fetch(`${base}/${locale}`, { next: { revalidate: 60 } });
      if (!res.ok) return null;
      const p = (await res.json()) as { content?: Json };
      if (p?.content && typeof p.content === "object") return p.content;
    } catch {
      /* fall through to local */
    }
    return null;
  }

  const content = await fetchContent();
  return content ? deepMerge(local, cmsToMessages(content)) : local;
}
