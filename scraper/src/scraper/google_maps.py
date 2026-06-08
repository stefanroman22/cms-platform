"""Playwright-based Google Maps scraper.

All DOM access goes through scraper.selectors. All extracted values are
funnelled through the Lead Pydantic model. No business logic here — the
pipeline orchestrates, the engine just scrapes.
"""

from __future__ import annotations

import asyncio
import random
import re
from collections import deque
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

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
from .categories import DEFAULT_CATEGORIES
from .config import settings
from .dedup import (
    classify_web_presence,
    external_id_from_url,
    normalize_name,
    parse_latlng_from_url,
    peek_external_id,
)
from .geo import bbox_for_place, grid_centers, split_cell
from .models import Lead, ScrapeFilters, ScrapeParams
from .urls import canonicalize_place_url, expand_if_short

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


async def _warm_up(page: Page, language: str, country: str) -> None:
    """Prime a fresh browser context before a direct-url scrape: load Maps once
    and accept consent. A cold context hits the consent interstitial ON the place
    URL and then renders the title but NOT the tab strip — so the Reviews tab
    never opens and all reviews are lost. Warming up (consent handled on the home
    page first, cookie shared context-wide) makes the place load cleanly with its
    tabs. Best-effort; failures don't abort the scrape. The search-feed path
    already warms the context via its feed navigation, so this is direct-url only."""
    try:
        await page.goto(
            f"https://www.google.com/maps?hl={language}&gl={country}",
            wait_until="domcontentloaded",
            timeout=20_000,
        )
        await _accept_consent(page)
        await page.wait_for_timeout(2000)
    except Exception as exc:  # noqa: BLE001 — warm-up is best-effort
        logger.debug("warm-up navigation failed (continuing): {}", exc)


def _text_has_end_sentinel(text: str) -> bool:
    """True if `text` contains any end-of-list sentinel (case-insensitive)."""
    low = text.lower()
    return any(sentinel in low for sentinel in selectors.RESULTS_END_TEXTS)


async def _feed_has_end_text(page: Page) -> bool:
    """Read the results feed's text and check for an end-of-list sentinel.
    Complements the fragile obfuscated end-marker class."""
    try:
        feed = page.locator(selectors.RESULTS_FEED)
        if await feed.count() == 0:
            return False
        return _text_has_end_sentinel(await feed.inner_text())
    except Exception:
        return False


async def _collect_place_links(page: Page, max_results: int) -> tuple[list[str], bool]:
    """Scroll the left feed until end-marker, stable count, or max reached.

    Returns (up to max_results distinct place URLs, saturated). `saturated` is
    True when the cap was hit without reaching the end of the list — Google had
    more results than it showed, so the cell should be subdivided."""
    links: list[str] = []
    seen: set[str] = set()
    stable_rounds = 0
    last_count = 0
    reached_end = False

    feed = page.locator(selectors.RESULTS_FEED)
    try:
        await feed.wait_for(timeout=8000)
    except Exception:
        # Single-result redirect: Google sent us straight to a place page.
        if "/place/" in page.url:
            return [page.url], False
        return [], False

    while len(links) < max_results and stable_rounds < 5:
        anchors = await page.locator(selectors.RESULTS_ITEM_LINK).element_handles()
        for a in anchors:
            href = await a.get_attribute("href")
            if href and href not in seen:
                seen.add(href)
                links.append(href)
                if len(links) >= max_results:
                    break

        end_marker = page.locator(selectors.RESULTS_END_MARKER)
        if await end_marker.count() > 0 or await _feed_has_end_text(page):
            logger.debug("reached end-of-list marker")
            reached_end = True
            break

        if len(links) == last_count:
            stable_rounds += 1
        else:
            stable_rounds = 0
        last_count = len(links)

        await feed.evaluate("(el) => el.scrollBy(0, Math.floor(el.clientHeight * 0.8))")
        await _polite_delay()

    saturated = len(links) >= max_results and not reached_end
    return links[:max_results], saturated


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
    """Read the 7-day hours. Primary source is the per-day 'copy open hours'
    buttons (data-value='Day, hours') which exist in the DOM regardless of the
    week dropdown's collapsed/expanded state. Falls back to the weekday table."""
    # Primary: copy-buttons carry a visibility-independent data-value.
    try:
        btns = await page.locator(selectors.PLACE_HOURS_COPY_BUTTONS).element_handles()
        pairs = [dv for b in btns if (dv := await b.get_attribute("data-value"))]
        parsed = _parse_hours_pairs(pairs)
        if parsed:
            return parsed
    except Exception:
        pass
    # Fallback: weekday table — first cell is the day, second the hours.
    try:
        rows = await page.locator(f"{selectors.PLACE_HOURS_TABLE} tr").element_handles()
        pairs = []
        for r in rows:
            cells = await r.query_selector_all("td")
            if len(cells) >= 2:
                day = (await cells[0].inner_text()).strip()
                hours = (await cells[1].inner_text()).strip()
                if day and hours:
                    pairs.append(f"{day}, {hours}")
        return _parse_hours_pairs(pairs)
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


async def _open_reviews_tab(page: Page) -> bool:
    """Click the Reviews tab and wait for cards to render. Returns True on
    success, False when the tab isn't present or doesn't open.

    The Overview tab strip (Overview/Reviews/About) renders a beat AFTER the
    place <h1>, so we WAIT for the tab to appear rather than checking instantly:
    an instant count()==0 raced the cold load and bailed ~1 in 5 visits, losing
    all reviews even for places that have them."""
    try:
        tab = page.locator(selectors.REVIEWS_TAB_BUTTON).first
        try:
            await tab.wait_for(state="visible", timeout=5000)
        except Exception:
            return False  # genuinely no reviews tab (e.g. a place with no reviews)
        await tab.click(timeout=2000)
        await page.wait_for_selector(selectors.REVIEW_CARD, timeout=5000)
        return True
    except Exception:
        return False


async def _sort_reviews_newest(page: Page) -> bool:
    """Switch the reviews sort to 'Newest'. Returns True on success, False when
    there is no sort control (few-review places) or the sort can't be applied.

    Guards the original bug: clicking the sort button the instant the first card
    renders is too early — the control isn't actionable yet. We wait for the
    button to be visible, open the menu, wait for the radio items, then click the
    localised 'Newest' option."""
    sort_btn = page.locator(selectors.REVIEW_SORT_BUTTON).first
    try:
        await sort_btn.wait_for(state="visible", timeout=4000)
    except Exception:
        logger.debug("no reviews sort control (few reviews) — keeping default order")
        return False
    try:
        # The reviews pane animates in after the tab opens; clicking the sort
        # control before it settles silently no-ops (the original bug). A fixed
        # settle beat — proven necessary in live testing — is the real fix.
        await page.wait_for_timeout(2000)
        await sort_btn.click(timeout=5000)
        await page.wait_for_timeout(600)  # let the dropdown render
        newest_re = re.compile("|".join(selectors.REVIEW_SORT_NEWEST_TEXTS), re.IGNORECASE)
        await (
            page.locator(selectors.REVIEW_SORT_MENUITEM)
            .filter(has_text=newest_re)
            .first.click(timeout=5000)
        )
        await page.wait_for_timeout(1200)  # client-side reorder
        logger.debug("reviews sorted by Newest")
        return True
    except Exception as exc:  # noqa: BLE001 — best-effort; caller still extracts
        logger.warning("reviews sort to Newest failed: {}", exc)
        return False


async def _review_rating(card: ElementHandle) -> int | None:
    try:
        star = await card.query_selector(selectors.REVIEW_RATING)
        if star is None:
            return None
        return _parse_star_rating(await star.get_attribute("aria-label"))
    except Exception:
        return None


async def _expand_review(card: ElementHandle) -> None:
    """Reveal the original language (undo Google's auto-translation) and
    expand truncated text, so the stored review is the full original text."""
    try:
        see_original = await card.query_selector(selectors.REVIEW_SEE_ORIGINAL)
        if see_original is not None:
            before = await _card_text(card, selectors.REVIEW_TEXT)
            await see_original.click(timeout=1500)
            # The translated→original swap is client-side and may lag a beat;
            # poll up to ~1.5s for the text to actually change before reading.
            for _ in range(15):
                await asyncio.sleep(0.1)
                if (await _card_text(card, selectors.REVIEW_TEXT)) != before:
                    break
    except Exception:
        pass
    # Click a "More"/"See more" button by text — class is volatile.
    try:
        await card.evaluate("""(el) => {
                const b = [...el.querySelectorAll('button')].find((x) => {
                    const t = (x.getAttribute('aria-label') || x.innerText || '')
                        .trim().toLowerCase();
                    return t === 'more' || t === 'see more';
                });
                if (b) b.click();
            }""")
    except Exception:
        pass


_REVIEW_SCAN_CAP = 12  # newest cards to scan when hunting for high-rated reviews


def _select_reviews(candidates: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    """From newest-first candidate reviews (each already >=4-star, with text),
    prefer 5-star and backfill with 4-star, up to `limit`. Newest order is
    preserved within each rating tier. Pure — unit-tested."""
    five = [c for c in candidates if c.get("rating") == 5]
    four = [c for c in candidates if c.get("rating") == 4]
    return (five + four)[:limit]


async def _extract_reviews(page: Page, limit: int) -> list[dict[str, Any]]:
    """Return up to 3 reviews with text, sorted newest-first, preferring 5-star
    and backfilling with 4-star (never below 4) so businesses without 5-star
    reviews still yield their best recent ones. `limit` is kept for API
    compatibility — the count is fixed at 3."""
    if not await _open_reviews_tab(page):
        return []
    await _sort_reviews_newest(page)  # best-effort; reviews still extracted if absent

    cards = await page.locator(selectors.REVIEW_CARD).element_handles()
    candidates: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    five_count = 0
    for card in cards[:_REVIEW_SCAN_CAP]:
        rid = await card.get_attribute("data-review-id")
        if rid:
            if rid in seen_ids:
                continue
            seen_ids.add(rid)
        rating = await _review_rating(card)
        if rating is None or rating < 4:
            continue
        await _expand_review(card)
        text = await _card_text(card, selectors.REVIEW_TEXT)
        if not text:
            continue  # skip rating-only reviews
        author = await card.get_attribute("aria-label") or await _card_text(
            card, selectors.REVIEW_AUTHOR
        )
        candidates.append(
            {
                "author": author,
                "text": text,
                "relative_date": await _card_text(card, selectors.REVIEW_RELATIVE_DATE),
                "rating": rating,
            }
        )
        if rating == 5:
            five_count += 1
            if five_count >= 3:
                break  # three newest 5-star reviews — can't do better
    return _select_reviews(candidates, 3)


def _about_available(aria: str) -> bool:
    """Google encodes a negated attribute as 'No <thing>' in the attribute
    span's aria-label (e.g. 'No delivery'). Everything else ('Has X',
    'Accepts X', 'Good for X') means the attribute is available."""
    return re.match(r"^no\b", (aria or "").strip(), re.IGNORECASE) is None


def _group_about_items(items: list[dict[str, Any]]) -> dict[str, dict[str, bool]]:
    """Group flat About items [{section,label,aria}] into
    {section: {label: available_bool}}. Empty labels are dropped."""
    out: dict[str, dict[str, bool]] = {}
    for it in items:
        label = (it.get("label") or "").strip()
        if not label:
            continue
        section = (it.get("section") or "Other").strip() or "Other"
        out.setdefault(section, {})[label] = _about_available(it.get("aria") or label)
    return out


_ABOUT_EXTRACT_JS = """() => {
    const panel = document.querySelector('div[role="region"][aria-label^="About"]');
    if (!panel) return [];
    const items = [];
    let section = "Other";
    for (const node of panel.querySelectorAll('h2, ul li')) {
        if (node.tagName.toLowerCase() === 'h2') {
            section = (node.innerText || '').trim() || section;
            continue;
        }
        const span = node.querySelector('span[aria-label]');
        if (!span) continue;
        const label = (span.innerText || '').trim();
        if (!label) continue;
        items.push({ section, label, aria: span.getAttribute('aria-label') || label });
    }
    return items;
}"""


async def _extract_about_attributes(page: Page) -> dict[str, dict[str, bool]]:
    """Open the About tab and read attributes grouped by section heading.
    Returns {} when the tab is absent or the panel never renders.

    Shape: {"Service options": {"In-store shopping": True, "Delivery": False}, ...}
    """
    try:
        btn = page.locator(selectors.ABOUT_TAB_BUTTON).first
        if await btn.count() == 0:
            return {}
        await btn.click(timeout=2000)
        # Wait for the *About* region specifically — never fall back to an
        # arbitrary region (the first region on the page is the map search box).
        await page.wait_for_selector(selectors.ABOUT_PANEL, timeout=4000)
        items = await page.evaluate(_ABOUT_EXTRACT_JS)
        return _group_about_items(items or [])
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


def _parse_hours_pairs(pairs: list[str]) -> dict[str, str] | None:
    """Map ['Thursday, 12–7 pm', 'Monday, Closed', ...] into the 7-day
    skeleton. Each entry is 'Day, hours' split on the FIRST ', ' so split
    daily hours ('9 am–12 pm, 1–5 pm') survive intact. Returns None when no
    weekday matched (so the caller can fall back to the placeholder skeleton)."""
    skeleton = _default_opening_hours()
    matched = False
    for raw in pairs:
        if not raw or ", " not in raw:
            continue
        day, hours = raw.split(", ", 1)
        day, hours = day.strip(), hours.strip()
        for canon in skeleton:
            if canon.lower() == day.lower():
                skeleton[canon] = hours
                matched = True
                break
    return skeleton if matched else None


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


def _parse_star_rating(aria: str | None) -> int | None:
    """Pull the integer star count from a review star aria-label such as
    '5 stars' / '1 star' / '4,0 sterren'. Returns None if no digit present."""
    if not aria:
        return None
    m = re.search(r"(\d+)", aria)
    return int(m.group(1)) if m else None


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
        await page.goto(
            _with_hl(url, params.language), wait_until="domcontentloaded", timeout=20_000
        )
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
        # Prefer the resolved page URL (Google rewrites it to include !3d/!4d
        # coords once the place loads) — a canonicalised direct-url input may
        # carry no coords. Fall back to the input URL for the feed path.
        lat, lng = parse_latlng_from_url(page.url)
        if lat is None:
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


def _search_url(
    query: str,
    language: str,
    country: str,
    center: tuple[float, float] | None = None,
    zoom: int = 16,
) -> str:
    slug = _SPACE_RE.sub("+", query.strip())
    url = f"https://www.google.com/maps/search/{slug}/"
    if center is not None:
        lat, lng = center
        url += f"@{lat},{lng},{zoom}z"  # explicit viewport — supplies the geography
    return url + f"?hl={language}&gl={country}"


class GridTooLargeError(ValueError):
    """Raised when a region's grid exceeds max_cells (no checkpoint/resume yet)."""


def _build_grid_queries(
    params: ScrapeParams,
) -> list[tuple[str, tuple[float, float] | None, int]]:
    """Plan the scoped queries.

    Region/bbox mode → one bare-category query per grid cell × category, each
    scoped by a viewport centre. Otherwise → legacy text queries (centre=None).
    Returns a fully-materialised list so an oversized grid fails before any
    browser launch."""
    if params.bbox is not None or params.region is not None:
        if params.bbox is not None:
            bbox = params.bbox
        else:
            assert params.region is not None
            bbox = bbox_for_place(params.region, cache_path=Path(settings.SCRAPER_GEOCODE_CACHE))
        cats = params.categories or DEFAULT_CATEGORIES
        grid = list(grid_centers(*bbox, cell_km=params.grid_cell_km))
        logger.info(
            "grid plan: {} cells × {} categories = {} scoped queries",
            len(grid),
            len(cats),
            len(grid) * len(cats),
        )
        if params.max_cells and len(grid) > params.max_cells:
            raise GridTooLargeError(
                f"grid has {len(grid)} cells > max_cells={params.max_cells}; "
                "narrow --region/--bbox or raise --max-cells (0 = unlimited)"
            )
        return [(cat, center, params.grid_zoom) for center in grid for cat in cats]
    return [(query, None, params.grid_zoom) for query in _build_queries(params)]


def _with_hl(url: str, language: str) -> str:
    """Force the Google Maps UI language via the `hl` query param so place
    pages render in `language` (category, weekday names, attribute labels)
    instead of geo-defaulting to the local language (e.g. Dutch in NL).
    Overrides any existing hl; leaves the `data=!...` path blob untouched."""
    parts = urlparse(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "hl"]
    query.append(("hl", language))
    return urlunparse(parts._replace(query=urlencode(query)))


async def scrape(
    params: ScrapeParams,
    scrape_job_id: str | None = None,
    headless: bool | None = None,
) -> AsyncIterator[Lead]:
    """Top-level async generator. Yields Lead objects one at a time so
    sinks can stream and the pipeline can update counters in real time.

    When `params.direct_url` is set: skip the search/feed loop entirely
    and visit only that URL. Filters are bypassed — the caller explicitly
    chose this lead via the `scrape-url` CLI command.
    """
    use_headless = settings.SCRAPER_HEADLESS if headless is None else headless

    # Expand + validate direct_url BEFORE launching Chromium — a bad URL
    # should fail in ms via urllib, not after ~5s of browser startup.
    expanded_direct_url: str | None = None
    if params.direct_url:
        # Expand short links, then canonicalise to the Overview view (strip the
        # '!1b1' reviews deep-link + session query) so a URL copied from the
        # reviews panel still extracts the place title/details.
        expanded_direct_url = canonicalize_place_url(expand_if_short(params.direct_url))

    # Build the scoped-query plan BEFORE launching Chromium so a bad region or
    # oversized grid fails in ms (mirrors the direct_url pre-validation above).
    grid_queries: list[tuple[str, tuple[float, float] | None, int]] = []
    if expanded_direct_url is None:
        grid_queries = _build_grid_queries(params)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=use_headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = await _new_context(browser, params.language, params.country)
        page = await ctx.new_page()

        try:
            # ─── Single-URL mode ───────────────────────────────────────
            if expanded_direct_url is not None:
                # Warm the fresh context so the place renders its tab strip
                # (otherwise the Reviews tab never appears → 0 reviews).
                await _warm_up(page, params.language, params.country)
                logger.info("direct-url scrape: {}", expanded_direct_url)
                try:
                    lead = await _scrape_one_place(ctx, expanded_direct_url, params, scrape_job_id)
                except Exception as exc:  # noqa: BLE001 — surface but don't crash sinks
                    logger.warning("direct-url place {} failed: {}", expanded_direct_url, exc)
                    return
                if lead is not None:
                    yield lead
                return

            # ─── Search-feed mode (unchanged) ──────────────────────────
            # Run-wide dedup so cartesian queries (cities × areas) and overlapping
            # neighbourhoods don't yield the same business twice. Peek the feature
            # id BEFORE visiting to save the ~5-10s place-page cost.
            seen_ids: set[str] = set()
            work: deque[tuple[str, tuple[float, float] | None, int, float, int]] = deque(
                (q, c, z, params.grid_cell_km, 0) for q, c, z in grid_queries
            )
            while work:
                query_text, center, zoom, cell_km, depth = work.popleft()
                logger.info("query: {!r} @ {} (depth {})", query_text, center, depth)
                await page.goto(
                    _search_url(query_text, params.language, params.country, center, zoom),
                    wait_until="domcontentloaded",
                    timeout=20_000,
                )
                await _accept_consent(page)
                await _polite_delay()

                links, saturated = await _collect_place_links(page, params.max_results_per_area)
                logger.info(
                    "collected {} place links for {!r} (saturated={})",
                    len(links),
                    query_text,
                    saturated,
                )

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

                # Cell-split: a saturated viewport cell (not legacy text mode) is
                # subdivided into 4 quarter-cells at a tighter zoom, up to depth.
                if (
                    params.split_on_saturation
                    and saturated
                    and center is not None
                    and depth < params.max_split_depth
                ):
                    subs = list(split_cell(center[0], center[1], cell_km))
                    logger.info(
                        "cell saturated → splitting into {} sub-cells (depth {}→{})",
                        len(subs),
                        depth,
                        depth + 1,
                    )
                    for sub in subs:
                        work.append((query_text, sub, zoom + 1, cell_km / 2, depth + 1))
        finally:
            await ctx.close()
            await browser.close()
