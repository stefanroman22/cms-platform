# ADR-0012: Leads import from a Google Maps listing through Places API (New)

Status: Accepted
Date: 2026-10-11

## Context

A lead is created by hand today: the admin types business name, address, phone, hours, reviews
and so on into the Add-Lead drawer, and the `lead-to-design-prompt` skill then turns the row into
a website design prompt. Nearly all of that data is already on the business's Google Maps listing.
The old Google Maps scraper that used to fill `leads` was deleted on 2026-08-26 and nothing in the
live code touches Google today (`primary_source` still defaults to `'google_maps'` and
`source_url` is shown as "View on Google Maps").

What Google offers, from the official docs (checked 2026-10-11):

- **Places API (New)** `GET https://places.googleapis.com/v1/places/{place_id}` returns, per field
  mask: identity (`displayName`, `primaryType`, `primaryTypeDisplayName`, `types`,
  `businessStatus`, `googleMapsUri`, `googleMapsLinks`), address (`formattedAddress`,
  `shortFormattedAddress`, `addressComponents`, `postalAddress`, `location`, `plusCode`,
  `viewport`, `timeZone`, `utcOffsetMinutes`, `pureServiceAreaBusiness`), contact
  (`nationalPhoneNumber`, `internationalPhoneNumber`, `websiteUri`), hours
  (`regularOpeningHours`, `regularSecondaryOpeningHours`), reputation (`rating`,
  `userRatingCount`, `reviews` — at most 5 — `reviewSummary`), descriptions
  (`editorialSummary`, `generativeSummary` with a mandatory `disclosureText`,
  `neighborhoodSummary`), pricing (`priceLevel`, `priceRange`), "About" attributes
  (`accessibilityOptions`, `parkingOptions`, `paymentOptions`, `dineIn`, `takeout`, `delivery`,
  `curbsidePickup`, `reservable`, `outdoorSeating`, `liveMusic`, `restroom`, `goodForChildren`,
  `goodForGroups`, `goodForWatchingSports`, `allowsDogs`, `menuForChildren`, `serves*`) and
  `photos` (at most 10; a resource `name`, size, `authorAttributions`, `googleMapsUri`).
  Requesting any Enterprise + Atmosphere field bills the whole request at that SKU.
- **Place Photos (New)** `GET https://places.googleapis.com/v1/{photo.name}/media?maxWidthPx=…`
  redirects to the image, or with `skipHttpRedirect=true` returns `{name, photoUri}`. Photo names
  must not be cached; one call per photo.
- **Maps Tools Resolution API** `POST https://mapstools.googleapis.com/v1:resolveMapsUrls`
  turns `maps.app.goo.gl/…` and `google.com/maps/place/…` URLs into place IDs (not `?q=` search
  URLs). Billed at $0, 600 queries/minute/project.
- **Text Search (New)** `POST https://places.googleapis.com/v1/places:searchText` finds
  candidates for a free-text query with an optional location bias; results are not guaranteed to
  be a single match.
- **Social media links, email and menu URL are not exposed by any Places API field.** The
  Business Profile UI has a social-links field, but it never reaches the API.

Cost and access:

- An API key from a Cloud project with **billing enabled (a card on file)** is mandatory; there
  is no key-less path. Scraping the Maps website is forbidden by the Terms (3.2.3a).
- Free monthly usage per SKU (since March 2025, replacing the $200 credit): Place Details
  Enterprise + Atmosphere 1,000 (then $25/1,000), Place Photos 1,000 (then $7/1,000), Text
  Search Pro 5,000 (then $32/1,000), URL resolution unlimited. One import = 1 Details call + up to
  10 Photos calls, so roughly 90 imports a month cost nothing; overage is charged automatically.
- Rate limits are per method, per minute, per project and configurable in the Cloud console; at
  our volume they do not matter, but nothing on our side must be able to burn the quota.
- Policy: place IDs may be stored indefinitely; the Places policy otherwise says content must not
  be pre-fetched, cached or stored (lat/lng up to 30 days in the service terms). Photos and
  reviews need author attribution and a link back to Google Maps.

## Decision

- **One button, official API.** The Add-Lead drawer gets an "Import from Google Maps" field that
  accepts a Maps URL, a short link, a raw place ID or free text (business name + city). The
  backend resolves it (raw ID → Resolution API → Text Search fallback that returns candidates to
  pick from), calls Place Details once with the full field mask above (Enterprise + Atmosphere),
  fetches up to `GOOGLE_PLACES_MAX_PHOTOS` photos, enriches from the business's own website, and
  creates the lead. An existing lead can be re-imported from its detail drawer.
- **Endpoints** on the existing admin leads router (`admin_user_via_bearer_or_sid`):
  `POST /admin/leads/google-import {input, lead_type?, language?}` → `201 LeadOut`, or
  `200 {status:"candidates", candidates:[{place_id,name,address}]}`, or `409` with the existing
  `lead_id` when the place is already a lead; `POST /admin/leads/{id}/google-import
{input?, overwrite?}` → `200 LeadOut`. `503` when `GOOGLE_MAPS_API_KEY` is empty.
- **Guard rails.** `pg_rate_limit.enforce` limits each admin to 20 imports/hour. A global
  calendar-month (UTC) counter in its own table `google_import_usage`, incremented atomically by
  the function `google_import_hit`, caps imports at `GOOGLE_PLACES_MONTHLY_CAP` (default 90, which
  keeps Details and Photos inside the free tier at 10 photos per import). It lives outside
  `rate_limits`, so the nightly rate-limit cleanup never resets it, and it fails closed: if the
  counter can't be read or written, the import is refused with `503`. A free-text search also
  consumes a slot (Text Search is billed), so a text search that then imports uses two. Every
  outbound call uses `urllib.request` with a 10 s timeout like `services/email_send.py`; no new
  Python dependency. Google errors map to 502/404/503/504, never 500.
- **Website enrichment is where social links come from.** If `websiteUri` is a real site the
  backend fetches its HTML (http/https only, DNS-resolved host must not be private/loopback/
  link-local, redirects re-checked, 8 s timeout, 1 MB cap, stdlib `html.parser`) and extracts
  Facebook, Instagram, TikTok, LinkedIn, YouTube, X, Pinterest and WhatsApp links from `<a href>`
  and JSON-LD `sameAs`, a `mailto:` email, `<meta name=description>`/`og:description` and
  `<html lang>`. If `websiteUri` is itself a Facebook/Instagram page it becomes that social link
  and `web_presence='social_only'`. Enrichment failures are warnings, never import failures.
- **Schema, additive only** (`backend/migrations/2026_10_11_lead_google_import.sql`):
  `google_place_id TEXT` (unique partial index), `google_imported_at TIMESTAMPTZ`,
  `business_status TEXT`, `primary_type TEXT`, `types TEXT[]`, `price_level TEXT`,
  `social_links JSONB NOT NULL DEFAULT '{}'`; plus the public Storage bucket `lead-photos`.
  Existing columns are reused: `business_name`←displayName, `category`←primaryTypeDisplayName,
  `about`←editorialSummary (fallback generativeSummary.overview), `description`←website meta
  description, `country`, `region`, `city`, `postal_code`←addressComponents, `address`←formattedAddress,
  `lat`, `lng`←location, `phone`←internationalPhoneNumber (fallback national),
  `website_url`←websiteUri, `facebook_url`/`instagram_url`←website enrichment (kept as columns
  for the existing UI and skill; `social_links` holds every platform), `email`←website enrichment,
  `web_presence`←none/social_only/has_website, `rating`, `review_count`, `reviews` (existing
  `{author, rating, text, relative_date}` shape plus `date`, `author_uri`, `author_photo_uri`,
  `google_maps_uri`), `opening_hours` (weekday descriptions into the existing `{Day: "hours"}`
  map), `photo_urls` (our Storage URLs), `source_url`←googleMapsUri, `external_id`=
  `google:<place_id>`, `primary_source`=`google_maps`, `extra.attributes` in the existing
  `{section: {attribute: bool}}` shape. Everything else lands in `extra.google` (address
  components, postal address, plus code, viewport, time zone, Maps links, price range,
  summaries with disclosure, raw opening-hour periods and secondary hours, the full attribute set,
  photo metadata with attributions, and the website-enrichment report).
- **Photos.** Each photo is downloaded at `maxWidthPx=1600` into `lead-photos/<lead_id>/<nn>-<hash>.<ext>`
  and its public URL appended to `photo_urls`; `extra.google.photos[]` keeps `name`, size,
  `attributions`, `google_maps_uri`, `storage_path`, `url` and `owner_photo` (true when the
  attribution display name matches the business name). Removing a photo through PATCH deletes
  the Storage object. The design-prompt skill treats owner photos as site assets and the rest as
  visual reference only.
- **Re-import semantics.** Default mode fills only empty fields; `rating`, `review_count`,
  `business_status`, `google_imported_at` and `extra.google` are always refreshed.
  `overwrite=true` replaces every Google-sourced field and re-downloads photos (old files
  deleted). Pipeline fields, `notes`, `design_prompt`, `languages`, `lead_type` and `menu_url`
  are never touched by an import.
- **Config.** `GOOGLE_MAPS_API_KEY` (optional; empty disables the feature), `GOOGLE_PLACES_MONTHLY_CAP`
  (90), `GOOGLE_PLACES_MAX_PHOTOS` (10) in `Settings`, `.env.example` and Vercel
  `cms-backend-roman`. The key is restricted to Places API (New) and Maps Tools Resolution API,
  with no HTTP-referrer restriction (server-side use).
- **Stance on stored content.** We store business facts the client confirms and owns when they
  sign (name, address, phone, hours), keep `google_place_id` so anything can be refreshed, keep
  author attribution and Maps links on every photo and review, and never show Google summaries
  as the business's own words. This is a pragmatic position, not a legal clearance; it is
  recorded here so it can be revisited.

## Consequences

- Creating a lead drops from ten minutes of typing to one paste; the design-prompt skill gets
  richer, more consistent input (attributes, price level, owner photos, every social link).
- The feature is off until a key exists; nothing else in the backend changes behaviour when
  `GOOGLE_MAPS_API_KEY` is empty.
- Spend is bounded by configuration, not by discipline: at the defaults the account stays inside
  the free tier, and raising `GOOGLE_PLACES_MONTHLY_CAP` is a deliberate act.
- Do NOT: call Google from the frontend or expose the key through the proxy; scrape
  google.com/maps HTML; store photo resource `name`s as if they were durable (they expire — keep
  them only as provenance); drop attribution when rendering photos or reviews; use
  `generativeSummary.overview` without its `disclosureText`; let an import write pipeline fields,
  `notes`, `design_prompt` or `languages`; add a Python dependency for HTML parsing or HTTP (stdlib
  only, so `requirements.lock` stays untouched).
