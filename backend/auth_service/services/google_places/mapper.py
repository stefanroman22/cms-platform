"""Pure mapping from a Place Details (New) response to lead columns (ADR-0012).
No I/O. Missing fields stay None/empty; nothing here raises on a sparse listing."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class MappedPlace:
    columns: dict
    attributes: dict[str, dict[str, bool]]
    google: dict
    photos: list[dict] = field(default_factory=list)
    website_uri: str | None = None


# Flat boolean attributes -> dashboard "About" sections (extra.attributes shape).
_FLAT_SECTIONS: dict[str, dict[str, str]] = {
    "Service options": {
        "dineIn": "Dine-in",
        "takeout": "Takeout",
        "delivery": "Delivery",
        "curbsidePickup": "Curbside pickup",
        "reservable": "Reservations",
    },
    "Amenities": {
        "outdoorSeating": "Outdoor seating",
        "restroom": "Restroom",
        "liveMusic": "Live music",
        "goodForWatchingSports": "Good for watching sports",
    },
    "Offerings": {
        "servesBreakfast": "Breakfast",
        "servesBrunch": "Brunch",
        "servesLunch": "Lunch",
        "servesDinner": "Dinner",
        "servesBeer": "Beer",
        "servesWine": "Wine",
        "servesCocktails": "Cocktails",
        "servesCoffee": "Coffee",
        "servesDessert": "Dessert",
        "servesVegetarianFood": "Vegetarian options",
        "menuForChildren": "Kids' menu",
    },
    "Crowd": {"goodForChildren": "Good for kids", "goodForGroups": "Good for groups"},
    "Pets": {"allowsDogs": "Dogs allowed"},
}
# Nested option objects -> sections.
_NESTED_SECTIONS: dict[str, tuple[str, dict[str, str]]] = {
    "Accessibility": (
        "accessibilityOptions",
        {
            "wheelchairAccessibleParking": "Wheelchair accessible parking",
            "wheelchairAccessibleEntrance": "Wheelchair accessible entrance",
            "wheelchairAccessibleRestroom": "Wheelchair accessible restroom",
            "wheelchairAccessibleSeating": "Wheelchair accessible seating",
        },
    ),
    "Parking": (
        "parkingOptions",
        {
            "freeParkingLot": "Free parking lot",
            "paidParkingLot": "Paid parking lot",
            "freeStreetParking": "Free street parking",
            "paidStreetParking": "Paid street parking",
            "valetParking": "Valet parking",
            "freeGarageParking": "Free garage parking",
            "paidGarageParking": "Paid garage parking",
        },
    ),
    "Payments": (
        "paymentOptions",
        {
            "acceptsCreditCards": "Credit cards",
            "acceptsDebitCards": "Debit cards",
            "acceptsCashOnly": "Cash only",
            "acceptsNfc": "NFC mobile payments",
        },
    ),
}


def normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.lower()).strip()


def _text(obj: dict | None) -> str | None:
    if not isinstance(obj, dict):
        return None
    t = obj.get("text")
    return t.strip() if isinstance(t, str) and t.strip() else None


def _address_parts(components: list[dict] | None) -> dict:
    out = {"country": None, "region": None, "city": None, "postal_code": None}
    for comp in components or []:
        types = set(comp.get("types") or [])
        if "country" in types:
            out["country"] = comp.get("shortText") or comp.get("longText")
        elif "administrative_area_level_1" in types:
            out["region"] = comp.get("longText") or comp.get("shortText")
        elif "locality" in types or ("postal_town" in types and not out["city"]):
            out["city"] = comp.get("longText") or comp.get("shortText")
        elif "postal_code" in types:
            out["postal_code"] = comp.get("longText") or comp.get("shortText")
    return out


def _hours(regular: dict | None) -> dict[str, str] | None:
    descs = (regular or {}).get("weekdayDescriptions") or []
    out: dict[str, str] = {}
    for line in descs:
        day, sep, hours = str(line).partition(":")
        if sep and day.strip():
            out[day.strip()] = hours.strip()
    return out or None


def _reviews(raw: list[dict] | None) -> list[dict]:
    out = []
    for r in raw or []:
        author = r.get("authorAttribution") or {}
        out.append(
            {
                "author": author.get("displayName"),
                "rating": r.get("rating"),
                "text": _text(r.get("text")) or _text(r.get("originalText")),
                "relative_date": r.get("relativePublishTimeDescription"),
                "date": r.get("publishTime"),
                "author_uri": author.get("uri"),
                "author_photo_uri": author.get("photoUri"),
                "google_maps_uri": r.get("googleMapsUri"),
            }
        )
    return out


def _attributes(place: dict) -> dict[str, dict[str, bool]]:
    out: dict[str, dict[str, bool]] = {}
    for section, keys in _FLAT_SECTIONS.items():
        vals = {
            label: bool(place[k]) for k, label in keys.items() if isinstance(place.get(k), bool)
        }
        if vals:
            out[section] = vals
    for section, (obj_key, keys) in _NESTED_SECTIONS.items():
        obj = place.get(obj_key) or {}
        vals = {label: bool(obj[k]) for k, label in keys.items() if isinstance(obj.get(k), bool)}
        if vals:
            out[section] = vals
    return out


def _photos(raw: list[dict] | None) -> list[dict]:
    out = []
    for p in raw or []:
        if not p.get("name"):
            continue
        out.append(
            {
                "name": p["name"],
                "width_px": p.get("widthPx"),
                "height_px": p.get("heightPx"),
                "attributions": [
                    {
                        "name": a.get("displayName"),
                        "uri": a.get("uri"),
                        "photo_uri": a.get("photoUri"),
                    }
                    for a in (p.get("authorAttributions") or [])
                ],
                "google_maps_uri": p.get("googleMapsUri"),
            }
        )
    return out


def classify_web_presence(website_uri: str | None) -> tuple[str, dict[str, str]]:
    """A Facebook/Instagram page as 'website' means social_only; a real site has_website."""
    from .website_enrich import normalize_social_url, social_platform_of

    if not website_uri:
        return "none", {}
    platform = social_platform_of(website_uri)
    if platform in ("facebook", "instagram"):
        return "social_only", {platform: normalize_social_url(platform, website_uri)}
    return "has_website", {}


def map_place(place: dict, *, language: str = "en") -> MappedPlace:
    name = _text(place.get("displayName")) or "Unnamed business"
    website_uri = (place.get("websiteUri") or "").strip() or None
    presence, social = classify_web_presence(website_uri)
    price_level = place.get("priceLevel")
    addr = _address_parts(place.get("addressComponents"))
    loc = place.get("location") or {}
    gen = place.get("generativeSummary") or {}

    columns = {
        "business_name": name,
        "name_normalized": normalize_name(name),
        "category": _text(place.get("primaryTypeDisplayName")),
        "about": _text(place.get("editorialSummary")) or _text(gen.get("overview")),
        **addr,
        "address": place.get("formattedAddress"),
        "lat": loc.get("latitude"),
        "lng": loc.get("longitude"),
        "phone": place.get("internationalPhoneNumber") or place.get("nationalPhoneNumber"),
        "website_url": None if presence == "social_only" else website_uri,
        "web_presence": presence,
        "facebook_url": social.get("facebook"),
        "instagram_url": social.get("instagram"),
        "rating": place.get("rating"),
        "review_count": place.get("userRatingCount"),
        "reviews": _reviews(place.get("reviews")),
        "opening_hours": _hours(place.get("regularOpeningHours")),
        "business_status": place.get("businessStatus"),
        "primary_type": place.get("primaryType"),
        "types": list(place.get("types") or []),
        "price_level": (
            price_level.removeprefix("PRICE_LEVEL_").lower()
            if isinstance(price_level, str) and price_level != "PRICE_LEVEL_UNSPECIFIED"
            else None
        ),
        "source_url": place.get("googleMapsUri"),
    }

    google = {
        "place_id": place.get("id"),
        "language": language,
        "display_name": name,
        "short_formatted_address": place.get("shortFormattedAddress"),
        "address_components": place.get("addressComponents") or [],
        "postal_address": place.get("postalAddress"),
        "plus_code": place.get("plusCode"),
        "viewport": place.get("viewport"),
        "time_zone": (place.get("timeZone") or {}).get("id"),
        "utc_offset_minutes": place.get("utcOffsetMinutes"),
        "pure_service_area_business": bool(place.get("pureServiceAreaBusiness", False)),
        "maps_uri": place.get("googleMapsUri"),
        "maps_links": place.get("googleMapsLinks"),
        "primary_type_display_name": _text(place.get("primaryTypeDisplayName")),
        "price_range": place.get("priceRange"),
        "editorial_summary": _text(place.get("editorialSummary")),
        "generative_summary": (
            {"overview": _text(gen.get("overview")), "disclosure": _text(gen.get("disclosureText"))}
            if gen
            else None
        ),
        "review_summary": _text((place.get("reviewSummary") or {}).get("text")),
        "neighborhood_summary": place.get("neighborhoodSummary"),
        "opening_hours": {
            "periods": (place.get("regularOpeningHours") or {}).get("periods") or [],
            "weekday_descriptions": (place.get("regularOpeningHours") or {}).get(
                "weekdayDescriptions"
            )
            or [],
            "secondary": place.get("regularSecondaryOpeningHours") or [],
        },
        "website_uri": website_uri,
    }

    return MappedPlace(
        columns=columns,
        attributes=_attributes(place),
        google=google,
        photos=_photos(place.get("photos")),
        website_uri=website_uri,
    )
