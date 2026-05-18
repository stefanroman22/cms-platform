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
PLACE_ADDRESS_BUTTON = 'button[data-item-id="address"]'
PLACE_WEBSITE_BUTTON = 'a[data-item-id="authority"]'
PLACE_PHONE_BUTTON = 'button[data-item-id*="phone"]'
PLACE_MENU_BUTTON = 'a[data-item-id="menu"]'
PLACE_HOURS_BUTTON = 'div[data-item-id="oh"] button, button[data-item-id="oh"]'
PLACE_HOURS_TABLE = 'table[aria-label*="hours"], table[aria-label*="openingstijden"]'
PLACE_DESCRIPTION = "div.PYvSYb"  # FRAGILE — editorial summary

# Reviews tab.
REVIEWS_TAB_BUTTON = 'button[aria-label*="Reviews"], button[aria-label*="recensies"]'
REVIEW_CARD = "div[data-review-id]"
REVIEW_AUTHOR = "div.d4r55"  # FRAGILE
REVIEW_RATING = 'span[role="img"][aria-label*="star"], span[role="img"][aria-label*="ster"]'
REVIEW_RELATIVE_DATE = "span.rsqaWe"  # FRAGILE
REVIEW_TEXT = "span.wiI7pd, div[data-review-id] span[jscontroller]"

# Photos.
PHOTO_BUTTONS = "button[data-photo-index] img"
