/**
 * Resolves CMS-managed "site data" (images, hours, contact, brand) with a safe
 * fallback to the static `lib/site.ts` constants.
 *
 * `lib/cms-content.ts` injects a `site` namespace into the next-intl messages from
 * the live CMS payload. Components read the resolved values via this helper:
 *   - Server Components: `resolveSite(await getMessages())`
 *   - Client Components: `resolveSite(useMessages())`
 * If the CMS is unreachable or a service is empty, the static constant wins, so
 * the site never breaks.
 */

import {
  BUSINESS,
  HOURS,
  HERO_IMAGE,
  ABOUT_IMAGES,
  GALLERY_TEASER_IMAGES,
  GALLERY_IMAGES,
  INSTAGRAM_IMAGES,
} from "@/lib/site";
import { readTheme, type CmsTheme } from "@/lib/cms-rich-text";

export interface HoursRow {
  messageKey: string;
  shortKey: string;
  time: string | null;
  short: string | null;
}

export interface SiteContact {
  phoneDisplay: string;
  phoneHref: string;
  instagram: string; // full URL
  instagramHandle: string;
  addressLines: string[];
  routeUrl: string;
}

export interface SiteData {
  brandName: string;
  heroImage: string;
  /** CMS `hero_image.alt`; null when empty (callers fall back to the messages alt). */
  heroImageAlt: string | null;
  /** CMS `location_map_image`; null when empty (MapCard keeps its SVG map). */
  mapImage: string | null;
  mapImageAlt: string | null;
  aboutImages: string[];
  galleryTeaserImages: string[];
  galleryImages: { src: string; span: number }[];
  instagramImages: string[];
  hours: HoursRow[];
  contact: SiteContact;
  /** CMS `general_theme` (palette + fonts); null when absent. */
  theme: CmsTheme | null;
}

function telHref(phone: string): string {
  const digits = phone.replace(/[^\d+]/g, "");
  if (digits.startsWith("+")) return `tel:${digits}`;
  if (digits.startsWith("0")) return `tel:+31${digits.slice(1)}`; // NL local → E.164
  return `tel:${digits}`;
}

function igUrl(handle: string): string {
  return `https://www.instagram.com/${handle.trim().replace(/^@/, "")}/`;
}

function splitAddress(addr: string): string[] {
  // "Groenestraat 277, 6531 HK Nijmegen" → ["Groenestraat 277", "6531 HK Nijmegen"]
  const parts = addr
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  return parts.length >= 2 ? [parts[0], parts.slice(1).join(", ")] : [addr];
}

const str = (v: unknown): string | null =>
  typeof v === "string" && v.trim() ? v.trim() : null;

/** True when the URL path (ignoring query/hash) is an SVG; next/image must skip the optimizer for these. */
export const isSvgUrl = (url: string): boolean => /\.svg$/i.test(url.split(/[?#]/)[0]);

const strArr = (v: unknown, fallback: readonly string[]): string[] => {
  const arr = Array.isArray(v) ? (v.filter((x) => typeof x === "string" && x.trim() !== "") as string[]) : [];
  return arr.length ? arr : [...fallback];
};

export function resolveSite(messages: unknown): SiteData {
  const site = ((messages as Record<string, unknown> | null)?.site ?? {}) as Record<string, unknown>;

  // Hours: override only the TIMES from the CMS; keep the localized day labels
  // (messageKey/shortKey) and the Mon→Sun ordering from the static HOURS array.
  const cmsHours = Array.isArray(site.hours) ? (site.hours as Record<string, unknown>[]) : null;
  const hours: HoursRow[] = HOURS.map((row, i) => {
    const c = cmsHours?.[i];
    if (!c) return { ...row };
    const open = str(c.open);
    const close = str(c.close);
    if (!open || !close) return { ...row, time: null, short: null };
    return { ...row, time: `${open} — ${close}`, short: `${open.slice(0, 2)} — ${close.slice(0, 2)}` };
  });

  // Contact.
  const c = (site.contact ?? {}) as Record<string, unknown>;
  const cmsPhone = str(c.phone);
  const cmsIg = str(c.instagram);
  const cmsAddr = str(c.address);
  const cmsMaps = str(c.maps_url);
  const contact: SiteContact = {
    phoneDisplay: cmsPhone ?? BUSINESS.phoneDisplay,
    phoneHref: cmsPhone ? telHref(cmsPhone) : BUSINESS.phoneHref,
    instagramHandle: cmsIg ?? BUSINESS.instagramHandle,
    instagram: cmsIg ? igUrl(cmsIg) : BUSINESS.instagram,
    addressLines: cmsAddr ? splitAddress(cmsAddr) : [BUSINESS.street, `${BUSINESS.postcode} ${BUSINESS.city}`],
    routeUrl: cmsMaps ?? BUSINESS.routeUrl,
  };

  // Gallery (masonry) — flat CMS url list mapped onto the static span rhythm.
  const cmsGallery = Array.isArray(site.galleryImages)
    ? (site.galleryImages.filter((x) => typeof x === "string") as string[])
    : null;
  const galleryImages =
    cmsGallery && cmsGallery.length
      ? cmsGallery.map((src, i) => ({ src, span: GALLERY_IMAGES[i % GALLERY_IMAGES.length].span }))
      : GALLERY_IMAGES.map((g) => ({ src: g.src, span: g.span }));

  return {
    brandName: str(site.brandName) ?? BUSINESS.wordmark,
    heroImage: str(site.heroImage) ?? HERO_IMAGE,
    heroImageAlt: str(site.heroImageAlt),
    mapImage: str(site.mapImage),
    mapImageAlt: str(site.mapImageAlt),
    aboutImages: strArr(site.aboutImages, ABOUT_IMAGES),
    galleryTeaserImages: strArr(site.galleryTeaserImages, GALLERY_TEASER_IMAGES),
    instagramImages: strArr(site.instagramImages, INSTAGRAM_IMAGES),
    galleryImages,
    hours,
    contact,
    theme: readTheme(site.theme),
  };
}
