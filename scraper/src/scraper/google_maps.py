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
from .dedup import classify_web_presence, external_id_from_url, normalize_name
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
        return hours or None
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
    """Pull the three review fields out of one card. One async call per
    field keeps the control flow obvious; selectors live in
    `scraper.selectors`."""
    return {
        "author": await _card_text(card, selectors.REVIEW_AUTHOR),
        "text": await _card_text(card, selectors.REVIEW_TEXT),
        "relative_date": await _card_text(card, selectors.REVIEW_RELATIVE_DATE),
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
    """Open the Reviews tab if present, scrape up to `limit` reviews."""
    if not await _open_reviews_tab(page):
        return []

    cards = await page.locator(selectors.REVIEW_CARD).element_handles()
    reviews: list[dict[str, Any]] = []
    for card in cards[:limit]:
        reviews.append(await _review_from_card(card))
    return reviews


def _split_address(address: str | None) -> tuple[str | None, str | None]:
    """Crude best-effort split of the trailing comma-separated segment
    into (postal_code, city). Refined in a follow-up if needed."""
    if not address:
        return None, None
    tail = address.split(",")[-1].strip()
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


def _parse_review_count(aria_text: str | None) -> int | None:
    if not aria_text:
        return None
    digits = "".join(c for c in aria_text if c.isdigit())
    return int(digits) if digits else None


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

        title = await _safe_text(page, selectors.PLACE_TITLE) or ""
        if not title:
            logger.warning("no title for {} — skipping", url)
            return None

        normalized = normalize_name(title)
        address = await _safe_text(page, selectors.PLACE_ADDRESS_BUTTON)
        phone = await _safe_text(page, selectors.PLACE_PHONE_BUTTON)
        website_url = await _safe_attr(page, selectors.PLACE_WEBSITE_BUTTON, "href")
        category = await _safe_text(page, selectors.PLACE_CATEGORY_BUTTON)
        menu_url = await _safe_attr(page, selectors.PLACE_MENU_BUTTON, "href")
        description = await _safe_text(page, selectors.PLACE_DESCRIPTION)

        rating = _parse_rating(await _safe_text(page, selectors.PLACE_RATING_NUMBER))
        review_count = _parse_review_count(
            await _safe_attr(page, selectors.PLACE_REVIEW_COUNT_BUTTON, "aria-label")
        )

        opening_hours = await _extract_opening_hours(page)
        reviews = await _extract_reviews(page, params.review_limit) if params.with_reviews else None

        web_presence, fb_url, ig_url = classify_web_presence(website_url)
        postal_code, city = _split_address(address)

        # EXTENSION POINT: scrape the "About" tab for attribute toggles
        # (delivery, dine-in, wheelchair-accessible, etc.) and stash them
        # in `extra`. Skipped in v1 to keep the scrape fast.
        # EXTENSION POINT: download photos into Supabase Storage. v1
        # stores URLs only — extracting URLs here is left to a follow-up.
        extra: dict[str, Any] = {}

        return Lead(
            external_id=external_id_from_url(
                url,
                normalized_name=normalized,
                city=city,
                lat=None,
                lng=None,
            ),
            scrape_job_id=scrape_job_id,
            primary_source="google_maps",
            source_url=url,
            lead_type=params.lead_type,
            category=category,
            business_name=title,
            name_normalized=normalized,
            description=description,
            country=params.country,
            city=city,
            address=address,
            postal_code=postal_code,
            phone=phone,
            website_url=website_url if web_presence == "has_website" else None,
            facebook_url=fb_url,
            instagram_url=ig_url,
            menu_url=menu_url,
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
                    try:
                        lead = await _scrape_one_place(ctx, link, params, scrape_job_id)
                    except Exception as exc:  # noqa: BLE001 — per-place isolation
                        logger.warning("place {} failed: {}", link, exc)
                        continue

                    if lead is None:
                        continue
                    if not _passes_filters(lead, params.filters):
                        continue

                    yield lead
                    await _polite_delay()
        finally:
            await ctx.close()
            await browser.close()
