"""ALL Google Maps DOM selectors live here.

When Google rotates obfuscated class names (which happens), update this
file only — engine logic in google_maps.py stays untouched.

Preferences (most-stable first):
  1. aria-label
  2. role + data-*
  3. semantic structure (button containing svg, etc.)
  4. obfuscated CSS classes (fragile; mark FRAGILE)
"""

from __future__ import annotations

# Cookie consent (EU interstitial, multi-language).
CONSENT_ACCEPT_BUTTONS: tuple[str, ...] = (
    'button[aria-label*="Accept"]',
    'button[aria-label*="Alles accepteren"]',
    'button[aria-label*="Akzeptieren"]',
    'button[aria-label*="Accepter"]',
    'form[action*="consent"] button:has-text("Accept all")',
    'form[action*="consent"] button:has-text("Alles accepteren")',
)
CONSENT_REJECT_BUTTONS: tuple[str, ...] = (
    'button[aria-label*="Reject all"]',
    'button[aria-label*="Alles afwijzen"]',
)

# Results feed (left-hand list).
RESULTS_FEED = 'div[role="feed"]'
RESULTS_ITEM_LINK = "a.hfpxzc"  # FRAGILE — anchor per place
# FRAGILE — "You've reached the end of the list."
RESULTS_END_MARKER = "p.HlvSq, span.HlvSq"

# Single-result redirect (the URL becomes the place page directly).
PLACE_HEADER_SELECTOR = "h1[class]"  # any h1 with class signifies a place page

# Place detail panel.
PLACE_TITLE = "h1[class]"
PLACE_CATEGORY_BUTTON = 'button[jsaction*="category"]'  # FRAGILE
PLACE_RATING_NUMBER = 'div.F7nice > span > span[aria-hidden="true"]'  # FRAGILE
PLACE_REVIEW_COUNT_BUTTON = 'button[aria-label*="review"], button[jsaction*="reviewChart"]'
# Container around rating + count; inner_text typically reads "4.7\n(87)" or "4.7 (87)".
PLACE_RATING_BLOCK = "div.F7nice"
PLACE_ADDRESS_BUTTON = 'button[data-item-id="address"]'
PLACE_WEBSITE_BUTTON = 'a[data-item-id="authority"]'
PLACE_PHONE_BUTTON = 'button[data-item-id*="phone"]'
PLACE_MENU_BUTTON = 'a[data-item-id="menu"]'
# Hours: each day is a "copy open hours" button carrying data-value="Day, hours"
# (present in the DOM even when the week dropdown is visually collapsed).
PLACE_HOURS_COPY_BUTTONS = 'button[jsaction*="openhours"][data-value]'
# FRAGILE fallback — weekday table when copy-buttons are absent.
PLACE_HOURS_TABLE = "table.eK4R0e"
PLACE_DESCRIPTION = "div.PYvSYb"  # FRAGILE — editorial summary

# Reviews tab.
REVIEWS_TAB_BUTTON = (
    'button[aria-label^="Reviews for "],'
    'button[aria-label="Reviews"],'
    'button[aria-label*="recensies"],'
    '[role="tab"][aria-label^="Reviews for "],'
    '[role="tab"][aria-label="Reviews"],'
    'button[jsaction*="reviewChart"]'
)
# Outer review card only — it carries BOTH data-review-id and aria-label
# (the author name). The inner content wrapper also has data-review-id but no
# aria-label, so requiring aria-label de-duplicates each review.
REVIEW_CARD = "div[data-review-id][aria-label]"
REVIEW_AUTHOR = "div.d4r55"  # FRAGILE fallback; author is normally the card aria-label
REVIEW_RATING = 'span[role="img"][aria-label*="star"], span[role="img"][aria-label*="ster"]'
REVIEW_RELATIVE_DATE = "span.rsqaWe"  # FRAGILE
REVIEW_TEXT = "span.wiI7pd"
# Sort control + "Newest" option.
REVIEW_SORT_BUTTON = 'button[aria-label="Sort reviews"], button[aria-label*="Sort"]'
REVIEW_SORT_MENUITEM = '[role="menuitemradio"]'
# Reveal the review's original language (Google auto-translates to the hl locale).
# This toggle is a role="switch" button whose label is visible TEXT ("Translated
# by Google ・ See original (…)"), NOT an aria-label — match its stable jsaction.
REVIEW_SEE_ORIGINAL = 'button[jsaction*="showReviewInOriginal"]'

# Photos.
PHOTO_BUTTONS = "button[data-photo-index] img"

# About tab — attribute toggles (Free Wi-Fi, Free breakfast, etc.).
# The tab is a button labelled "About" / "Over"; cards inside have
# aria-label containing the attribute name.
ABOUT_TAB_BUTTON = (
    'button[aria-label^="About "],'
    'button[aria-label="About"],'
    'button[aria-label*="Over "],'
    '[role="tab"][aria-label^="About "],'
    '[role="tab"][aria-label="About"]'
)

# The opened About tab renders a region whose aria-label starts with "About".
ABOUT_PANEL = 'div[role="region"][aria-label^="About"]'

# About-tab structure (best-effort): when the tab is opened, the right-
# hand panel contains rows. Each visible attribute exposes its label via
# `aria-label` on a `li`, OR is text inside a `div[role="img"]` icon row.
ABOUT_ATTRIBUTE_ITEMS = (
    'div[role="region"] li[aria-label],'
    'div[role="group"] li[aria-label],'
    'div[aria-label*="About"] li[aria-label]'
)
