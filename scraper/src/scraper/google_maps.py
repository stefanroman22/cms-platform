"""Playwright-based Google Maps scraper.

All DOM access goes through scraper.selectors. All extracted values are
funnelled through the Lead Pydantic model. No business logic here — the
pipeline orchestrates, the engine just scrapes.
"""

from __future__ import annotations

import asyncio
import random
import re
from collections.abc import AsyncIterator
from typing import Any

from loguru import logger
from playwright.async_api import (
    Browser,
    BrowserContext,
    ElementHandle,
    Page,
    async_playwright,
)
from tenacity import retry, stop_after_attempt, wait_exponential

from . import selectors
from .config import settings
from .dedup import (
    classify_web_presence,
    external_id_from_url,
    normalize_name,
    parse_latlng_from_url,
    peek_external_id,
)
from .models import Lead, ScrapeFilters, ScrapeParams

# ──────────────────────────────────────────────────────────────────────
# Helpers (timing + browser lifecycle)
# ──────────────────────────────────────────────────────────────────────


async def _polite_delay() -> None:
    """Randomised pacing between actions — avoids trivial bot fingerprints."""
    ms = random.randint(settings.SCRAPER_MIN_DELAY_MS, settings.SCRAPER_MAX_DELAY_MS)
    await asyncio.sleep(ms / 1000.0)


async def _new_context(browser: Browser, language: str, country: str) -> BrowserContext:
    """Locale + UA + the standard anti-detection bits.

    EXTENSION POINT: residential proxies — add a `proxy={"server": ...}`
    kwarg here when Google starts blocking the Hetzner IP.
    """
    # `country` is currently informational (only used to pick `gl=` on
    # search URLs); reserved as a parameter so a future per-region
    # context (geolocation/timezone) is a one-arg change.
    _ = country
    ctx = await browser.new_context(
        user_agent=settings.SCRAPER_USER_AGENT,
        locale=language,
        viewport={"width": 1366, "height": 900},
        timezone_id="Europe/Amsterdam",
        geolocation=None,
    )
    await ctx.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
    )
    return ctx


# ──────────────────────────────────────────────────────────────────────
# Consent + feed scrolling
# ──────────────────────────────────────────────────────────────────────


async def _accept_consent(page: Page) -> None:
    """EU interstitial — try each accept selector, give up after timeout."""
    for sel in selectors.CONSENT_ACCEPT_BUTTONS:
        try:
            await page.locator(sel).first.click(timeout=1500)
            logger.debug("clicked consent: {}", sel)
            await page.wait_for_load_state("networkidle", timeout=5000)
            return
        except Exception:
            continue
    logger.debug("no consent prompt visible")


async def _collect_place_links(page: Page, max_results: int) -> list[str]:
    """Scroll the left feed until end-marker, stable count, or max reached.

    Returns up to `max_results` distinct place URLs.
    """
    links: list[str] = []
    seen: set[str] = set()
    stable_rounds = 0
    last_count = 0

    feed = page.locator(selectors.RESULTS_FEED)
    try:
        await feed.wait_for(timeout=8000)
    except Exception:
        # Single-result redirect: Google sent us straight to a place page.
        if "/place/" in page.url:
            return [page.url]
        return []

    while len(links) < max_results and stable_rounds < 3:
        anchors = await page.locator(selectors.RESULTS_ITEM_LINK).element_handles()
        for a in anchors:
            href = await a.get_attribute("href")
            if href and href not in seen:
                seen.add(href)
                links.append(href)
                if len(links) >= max_results:
                    break

        end_marker = page.locator(selectors.RESULTS_END_MARKER)
        if await end_marker.count() > 0:
            logger.debug("reached end-of-list marker")
            break

        if len(links) == last_count:
            stable_rounds += 1
        else:
            stable_rounds = 0
        last_count = len(links)

        await feed.evaluate("(el) => el.scrollBy(0, el.scrollHeight)")
        await _polite_delay()

    return links[:max_results]


# ──────────────────────────────────────────────────────────────────────
# Page-level field extraction
# ──────────────────────────────────────────────────────────────────────


async def _safe_text(page: Page, selector: str) -> str | None:
    try:
        el = page.locator(selector).first
        if await el.count() == 0:
            return None
        return (await el.inner_text()).strip()
    except Exception:
        return None


async def _safe_attr(page: Page, selector: str, attr: str) -> str | None:
    try:
        el = page.locator(selector).first
        if await el.count() == 0:
            return None
        return await el.get_attribute(attr)
    except Exception:
        return None


async def _extract_opening_hours(page: Page) -> dict[str, str] | None:
    """Open the hours expansion if present, return {day_name: hours}."""
    try:
        btn = page.locator(selectors.PLACE_HOURS_BUTTON).first
        if await btn.count() == 0:
            return None
        await btn.click(timeout=2000)
        await page.wait_for_selector(selectors.PLACE_HOURS_TABLE, timeout=2000)
        rows = await page.locator(f"{selectors.PLACE_HOURS_TABLE} tr").element_handles()
        hours: dict[str, str] = {}
        for r in rows:
            cells = await r.query_selector_all("td, th")
            if len(cells) >= 2:
                day_text = (await cells[0].inner_text()).strip()
                value_text = (await cells[1].inner_text()).strip()
                if day_text:
                    hours[day_text] = value_text
        if not hours:
            return None
        # Merge into the skeleton so every canonical day key is present.
        skeleton = _default_opening_hours()
        for k, v in hours.items():
            for canon in skeleton.keys():
                if canon.lower() in k.lower():
                    skeleton[canon] = v
                    break
        return skeleton
    except Exception:
        return None


async def _card_text(card: ElementHandle, selector: str) -> str | None:
    """Query `selector` INSIDE a review card, return stripped text or None."""
    try:
        el = await card.query_selector(selector)
        if el is None:
            return None
        return (await el.inner_text()).strip()
    except Exception:
        return None


async def _review_from_card(card: ElementHandle) -> dict[str, Any]:
    """Pull author, text, relative_date, rating (1-5 int) out of one card.
    Rating is parsed from the aria-label on the star span (REVIEW_RATING
    selector); falls back to None if not parseable."""
    rating: int | None = None
    try:
        star_el = await card.query_selector(selectors.REVIEW_RATING)
        if star_el is not None:
            aria = await star_el.get_attribute("aria-label")
            if aria:
                import re

                m = re.search(r"(\d+)\s*(star|ster)", aria, re.IGNORECASE)
                if m:
                    rating = int(m.group(1))
    except Exception:
        rating = None
    return {
        "author": await _card_text(card, selectors.REVIEW_AUTHOR),
        "text": await _card_text(card, selectors.REVIEW_TEXT),
        "relative_date": await _card_text(card, selectors.REVIEW_RELATIVE_DATE),
        "rating": rating,
    }


async def _open_reviews_tab(page: Page) -> bool:
    """Click the Reviews tab and wait for cards to render. Returns True
    on success, False when the tab isn't present or doesn't open."""
    try:
        tab = page.locator(selectors.REVIEWS_TAB_BUTTON).first
        if await tab.count() == 0:
            return False
        await tab.click(timeout=2000)
        await page.wait_for_selector(selectors.REVIEW_CARD, timeout=3000)
        return True
    except Exception:
        return False


async def _extract_reviews(page: Page, limit: int) -> list[dict[str, Any]]:
    """Open the Reviews tab if present, return TOP 3 reviews by star
    rating. `limit` is ignored from the spec — kept as a no-op for API
    compatibility — we always return 3."""
    if not await _open_reviews_tab(page):
        return []

    # Cap candidates: scrolling the reviews pane would yield more, but
    # the top-rated are usually rendered first by Google's default sort.
    cards = await page.locator(selectors.REVIEW_CARD).element_handles()
    candidates: list[dict[str, Any]] = []
    for card in cards[:30]:
        candidates.append(await _review_from_card(card))

    # Sort by rating desc; None ratings sink to the bottom.
    candidates.sort(key=lambda r: (r.get("rating") or -1), reverse=True)
    return candidates[:3]


def _normalize_attribute_key(label: str) -> str:
    """Convert 'Free Wi-Fi' -> 'free_wifi', 'Pet-friendly' -> 'pet_friendly'."""
    import re

    cleaned = re.sub(r"[^\w\s]", " ", label.lower())
    cleaned = re.sub(r"\s+", "_", cleaned.strip())
    return cleaned


async def _extract_about_attributes(page: Page) -> dict[str, bool]:
    """Open the About tab and read each attribute as a boolean dict.
    Returns empty dict if the tab is absent or unparseable."""
    try:
        btn = page.locator(selectors.ABOUT_TAB_BUTTON).first
        if await btn.count() == 0:
            return {}
        await btn.click(timeout=2000)
        await page.wait_for_load_state("networkidle", timeout=3000)
        items = await page.locator(selectors.ABOUT_ATTRIBUTE_ITEMS).element_handles()
        attrs: dict[str, bool] = {}
        for it in items:
            label = await it.get_attribute("aria-label")
            if not label:
                continue
            # Google marks unavailable attributes with "No" prefix
            # (e.g. "No Wi-Fi"). Treat those as false.
            normalized = label.strip()
            if normalized.lower().startswith("no "):
                key = _normalize_attribute_key(normalized[3:].strip())
                attrs[key] = False
            else:
                attrs[_normalize_attribute_key(normalized)] = True
        return attrs
    except Exception:
        return {}


_DUTCH_POSTAL_RE = re.compile(r"^(\d{4}\s?[A-Z]{2})\s+(.+)$")


def _strip_icon_prefix(text: str | None) -> str | None:
    """Strip leading private-use-area chars + leading whitespace.
    Google Maps prefixes some labels with icon-font glyphs (U+E000-U+F8FF)
    followed by a newline."""
    if text is None:
        return None
    cleaned = text.lstrip()
    i = 0
    while i < len(cleaned) and ("" <= cleaned[i] <= "" or cleaned[i].isspace()):
        i += 1
    return cleaned[i:].strip() or None


def _default_opening_hours() -> dict[str, str]:
    """7-day skeleton with `___` placeholders. Used when extraction
    misses (selector drift or place has no hours block) so downstream
    consumers (website builder agent, dashboard) always see all days."""
    return {
        "Monday": "___",
        "Tuesday": "___",
        "Wednesday": "___",
        "Thursday": "___",
        "Friday": "___",
        "Saturday": "___",
        "Sunday": "___",
    }


def _split_address(address: str | None) -> tuple[str | None, str | None]:
    """Best-effort split of the trailing comma-separated segment into
    (postal_code, city). Handles Dutch `NNNN AA City` postal-code format
    explicitly; falls back to the prior whitespace split otherwise."""
    if not address:
        return None, None
    tail = address.split(",")[-1].strip()
    m = _DUTCH_POSTAL_RE.match(tail)
    if m:
        return m.group(1), m.group(2).strip()
    parts = tail.split(None, 1)
    if len(parts) == 2 and any(ch.isdigit() for ch in parts[0]):
        return parts[0], parts[1]
    return None, tail or None


def _parse_rating(rating_text: str | None) -> float | None:
    if not rating_text:
        return None
    try:
        return float(rating_text.replace(",", "."))
    except ValueError:
        return None


def _parse_review_count(text: str | None) -> int | None:
    """Pull the review count from one of several Google Maps surfaces:

    - aria-label on the review button: `"4.7 stars 87 Reviews"` → 87
    - inner_text on the same button: `"87"` or `"(87)"` → 87
    - rating block's inner_text: `"4.7\\n(87)"` → 87
    - rating block without count: `"4.7"` → None (NOT 7)

    Strategy: prefer a parenthesised `(N)` (the visible "(87)" form);
    fall back to "N review(s)" pattern; otherwise None. Plain digit
    runs without context are ambiguous (could be a rating digit) so
    we refuse to guess."""
    if not text:
        return None
    paren = re.search(r"\((\d[\d.,]*)\)", text)
    if paren:
        return int(paren.group(1).replace(",", "").replace(".", ""))
    near_word = re.search(r"(\d[\d.,]*)\s*review", text, re.IGNORECASE)
    if near_word:
        return int(near_word.group(1).replace(",", "").replace(".", ""))
    return None


# ──────────────────────────────────────────────────────────────────────
# Place-page → Lead
# ──────────────────────────────────────────────────────────────────────


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
async def _scrape_one_place(
    ctx: BrowserContext,
    url: str,
    params: ScrapeParams,
    scrape_job_id: str | None,
) -> Lead | None:
    page = await ctx.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
        await _accept_consent(page)
        await page.wait_for_selector(selectors.PLACE_TITLE, timeout=10_000)
        await _polite_delay()

        title = _strip_icon_prefix(await _safe_text(page, selectors.PLACE_TITLE)) or ""
        if not title:
            logger.warning("no title for {} — skipping", url)
            return None

        normalized = normalize_name(title)
        address = _strip_icon_prefix(await _safe_text(page, selectors.PLACE_ADDRESS_BUTTON))
        phone = _strip_icon_prefix(await _safe_text(page, selectors.PLACE_PHONE_BUTTON))
        website_url = await _safe_attr(page, selectors.PLACE_WEBSITE_BUTTON, "href")
        category = _strip_icon_prefix(await _safe_text(page, selectors.PLACE_CATEGORY_BUTTON))
        description = _strip_icon_prefix(await _safe_text(page, selectors.PLACE_DESCRIPTION))

        rating = _parse_rating(await _safe_text(page, selectors.PLACE_RATING_NUMBER))
        review_count = _parse_review_count(
            await _safe_attr(page, selectors.PLACE_REVIEW_COUNT_BUTTON, "aria-label")
        )
        if review_count is None:
            # Fallback 1: button inner_text often reads "87" or "(87)".
            review_count = _parse_review_count(
                await _safe_text(page, selectors.PLACE_REVIEW_COUNT_BUTTON)
            )
        if review_count is None:
            # Fallback 2: rating block's inner_text usually reads "4.7\n(87)".
            block_text = await _safe_text(page, selectors.PLACE_RATING_BLOCK)
            review_count = _parse_review_count(block_text)

        opening_hours = await _extract_opening_hours(page) or _default_opening_hours()
        reviews = await _extract_reviews(page, params.review_limit) if params.with_reviews else None

        web_presence, fb_url, ig_url = classify_web_presence(website_url)
        postal_code, city = _split_address(address)
        lat, lng = parse_latlng_from_url(url)

        about_attrs = await _extract_about_attributes(page)

        # Substitute fallback strings for null text fields the user
        # wants to see in the UI rather than "—".
        def _or_not_found(v: str | None) -> str:
            return v if v else "Not found"

        # EXTENSION POINT: download photos into Supabase Storage. v1
        # stores URLs only — extracting URLs here is left to a follow-up.
        extra: dict[str, Any] = {}
        if about_attrs:
            extra["attributes"] = about_attrs

        return Lead(
            external_id=external_id_from_url(
                url,
                normalized_name=normalized,
                city=city,
                lat=lat,
                lng=lng,
            ),
            scrape_job_id=scrape_job_id,
            primary_source="google_maps",
            source_url=url,
            lead_type=params.lead_type,
            category=_or_not_found(category),
            business_name=title,
            name_normalized=normalized,
            description=_or_not_found(description),
            country=params.country,
            city=city,
            address=address,
            postal_code=postal_code,
            lat=lat,
            lng=lng,
            phone=phone,
            website_url=website_url if web_presence == "has_website" else None,
            facebook_url=fb_url,
            instagram_url=ig_url,
            menu_url=None,  # spec: stop populating; field kept on model for back-compat
            web_presence=web_presence,  # type: ignore[arg-type]
            rating=rating,
            review_count=review_count,
            reviews=reviews,
            opening_hours=opening_hours,
            extra=extra,
        )
    finally:
        await page.close()


# ──────────────────────────────────────────────────────────────────────
# Filter application
# ──────────────────────────────────────────────────────────────────────


def _passes_filters(lead: Lead, f: ScrapeFilters) -> bool:
    if f.web_presence and lead.web_presence not in f.web_presence:
        return False
    if f.min_rating is not None and (lead.rating or 0) < f.min_rating:
        return False
    if f.max_rating is not None and (lead.rating or 0) > f.max_rating:
        return False
    if f.min_reviews is not None and (lead.review_count or 0) < f.min_reviews:
        return False
    if f.max_reviews is not None and (lead.review_count or 0) > f.max_reviews:
        return False
    return True


# ──────────────────────────────────────────────────────────────────────
# Query building + top-level scrape
# ──────────────────────────────────────────────────────────────────────


def _build_queries(params: ScrapeParams) -> list[str]:
    """Cartesian: cities × areas, falling back to country."""
    queries: list[str] = []
    if not params.cities:
        queries.append(f"{params.category} in {params.country}")
        return queries
    for city in params.cities:
        if not params.areas:
            queries.append(f"{params.category} in {city}")
        else:
            for area in params.areas:
                queries.append(f"{params.category} in {area}, {city}")
    return queries


_SPACE_RE = re.compile(r"\s+")


def _search_url(query: str, language: str, country: str) -> str:
    slug = _SPACE_RE.sub("+", query.strip())
    return f"https://www.google.com/maps/search/{slug}/?hl={language}&gl={country}"


async def scrape(
    params: ScrapeParams,
    scrape_job_id: str | None = None,
    headless: bool | None = None,
) -> AsyncIterator[Lead]:
    """Top-level async generator. Yields Lead objects one at a time so
    sinks can stream and the pipeline can update counters in real time.
    """
    use_headless = settings.SCRAPER_HEADLESS if headless is None else headless

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=use_headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = await _new_context(browser, params.language, params.country)
        page = await ctx.new_page()

        # Run-wide dedup so cartesian queries (cities × areas) and overlapping
        # neighbourhoods don't yield the same business twice. Peek the feature
        # id BEFORE visiting to save the ~5-10s place-page cost.
        seen_ids: set[str] = set()
        try:
            for query in _build_queries(params):
                logger.info("query: {}", query)
                await page.goto(
                    _search_url(query, params.language, params.country),
                    wait_until="domcontentloaded",
                    timeout=20_000,
                )
                await _accept_consent(page)
                await _polite_delay()

                links = await _collect_place_links(page, params.max_results_per_area)
                logger.info("collected {} place links for {!r}", len(links), query)

                for link in links:
                    # Pre-visit dedup: if URL carries a Google feature id and we
                    # already yielded that business in this run, skip without
                    # loading the page.
                    pre_id = peek_external_id(link)
                    if pre_id is not None and pre_id in seen_ids:
                        logger.debug("dedup pre-visit skip: {}", pre_id)
                        continue

                    try:
                        lead = await _scrape_one_place(ctx, link, params, scrape_job_id)
                    except Exception as exc:  # noqa: BLE001 — per-place isolation
                        logger.warning("place {} failed: {}", link, exc)
                        continue

                    if lead is None:
                        continue
                    # Post-visit safety net for URLs whose feature id was
                    # absent at pre-visit time (hash-fallback path).
                    if lead.external_id in seen_ids:
                        logger.debug("dedup post-visit skip: {}", lead.external_id)
                        continue
                    if not _passes_filters(lead, params.filters):
                        continue

                    seen_ids.add(lead.external_id)
                    yield lead
                    await _polite_delay()
        finally:
            await ctx.close()
            await browser.close()
