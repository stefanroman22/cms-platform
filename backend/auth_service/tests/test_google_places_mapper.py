import json
from pathlib import Path

from auth_service.services.google_places import mapper

FIX = Path(__file__).parent / "fixtures" / "google_place_details.json"


def _place():
    return json.loads(FIX.read_text(encoding="utf-8"))


def test_map_place_columns():
    m = mapper.map_place(_place())
    c = m.columns
    assert c["business_name"] == "Samir Kapsalon"
    assert c["name_normalized"] == "samir kapsalon"
    assert c["category"] == "Barber shop"
    assert c["about"] == "Modern barber shop with walk-ins."
    assert (c["country"], c["region"], c["city"], c["postal_code"]) == (
        "NL",
        "Flevoland",
        "Lelystad",
        "8232 ZX",
    )
    assert c["address"] == "Stadhuisplein 12, 8232 ZX Lelystad, Netherlands"
    assert (c["lat"], c["lng"]) == (52.5083, 5.4751)
    assert c["phone"] == "+31 320 123456"
    assert c["website_url"] == "https://samirkapsalon.nl/"
    assert c["web_presence"] == "has_website"
    assert c["facebook_url"] is None and c["instagram_url"] is None
    assert c["rating"] == 4.8 and c["review_count"] == 212
    assert c["business_status"] == "OPERATIONAL"
    assert c["primary_type"] == "barber_shop"
    assert c["types"] == ["barber_shop", "hair_salon", "point_of_interest", "establishment"]
    assert c["price_level"] == "moderate"
    assert c["source_url"] == "https://maps.google.com/?cid=1234567890"
    assert m.website_uri == "https://samirkapsalon.nl/"


def test_map_place_opening_hours_shape():
    m = mapper.map_place(_place())
    assert m.columns["opening_hours"]["Monday"] == "9:00 AM – 6:00 PM"
    assert m.columns["opening_hours"]["Sunday"] == "Closed"
    assert len(m.columns["opening_hours"]) == 7
    assert m.google["opening_hours"]["periods"][0]["open"]["day"] == 1


def test_map_place_reviews_shape():
    r = mapper.map_place(_place()).columns["reviews"][0]
    assert r == {
        "author": "Maria K.",
        "rating": 5,
        "text": "Beste kapper van Lelystad!",
        "relative_date": "2 months ago",
        "date": "2026-08-01T10:00:00Z",
        "author_uri": "https://www.google.com/maps/contrib/1",
        "author_photo_uri": "https://lh3.googleusercontent.com/a/1",
        "google_maps_uri": "https://www.google.com/maps/reviews/r1",
    }


def test_map_place_attributes_sections():
    a = mapper.map_place(_place()).attributes
    assert a["Accessibility"] == {
        "Wheelchair accessible entrance": True,
        "Wheelchair accessible restroom": False,
    }
    assert a["Parking"] == {"Free street parking": True}
    assert a["Payments"] == {"Credit cards": True, "NFC mobile payments": True, "Cash only": False}
    assert a["Amenities"] == {"Restroom": True}
    assert a["Crowd"] == {"Good for kids": True}
    assert a["Service options"] == {"Reservations": False}
    assert "Offerings" not in a  # nothing present in the fixture


def test_map_place_google_blob():
    g = mapper.map_place(_place()).google
    assert g["place_id"] == "ChIJsamir0000000000000000000"
    assert g["maps_links"]["directionsUri"].startswith("https://")
    assert g["generative_summary"] == {
        "overview": "A busy barber shop known for sharp fades.",
        "disclosure": "Summarized with Gemini",
    }
    assert g["review_summary"] == "People praise the fades."
    assert g["price_range"]["startPrice"]["units"] == "20"
    assert g["time_zone"] == "Europe/Amsterdam"
    assert g["address_components"][0]["types"] == ["street_number"]
    assert g["pure_service_area_business"] is False


def test_map_place_photos():
    p = mapper.map_place(_place()).photos
    assert len(p) == 2
    assert p[0] == {
        "name": "places/ChIJsamir/photos/p1",
        "width_px": 4032,
        "height_px": 3024,
        "attributions": [
            {
                "name": "Samir Kapsalon",
                "uri": "https://maps.google.com/maps/contrib/9",
                "photo_uri": "https://lh3.googleusercontent.com/a/9",
            }
        ],
        "google_maps_uri": "https://www.google.com/maps/place//photos/p1",
    }


def test_map_place_about_falls_back_to_generative():
    place = _place()
    del place["editorialSummary"]
    assert mapper.map_place(place).columns["about"] == "A busy barber shop known for sharp fades."


def test_map_place_minimal_listing():
    place = {
        "id": "ChIJmin",
        "displayName": {"text": "Mobile Dog Groomer"},
        "pureServiceAreaBusiness": True,
    }
    m = mapper.map_place(place)
    c = m.columns
    assert c["business_name"] == "Mobile Dog Groomer"
    assert c["web_presence"] == "none"
    assert c["phone"] is None and c["opening_hours"] is None and c["reviews"] == []
    assert c["country"] is None and c["rating"] is None and c["types"] == []
    assert m.attributes == {} and m.photos == [] and m.website_uri is None
    assert m.google["pure_service_area_business"] is True


def test_classify_web_presence_social_site():
    presence, links = mapper.classify_web_presence("https://www.facebook.com/samirkapsalon/")
    assert presence == "social_only"
    assert links == {"facebook": "https://www.facebook.com/samirkapsalon"}
    assert mapper.classify_web_presence(None) == ("none", {})
    assert mapper.classify_web_presence("https://samir.nl") == ("has_website", {})


def test_classify_web_presence_facebook_profile_php():
    url = "https://www.facebook.com/profile.php?id=100063512345678"
    assert mapper.classify_web_presence(url) == ("social_only", {"facebook": url})


def test_map_place_phone_falls_back_to_national():
    place = _place()
    del place["internationalPhoneNumber"]
    assert mapper.map_place(place).columns["phone"] == "0320 123456"
