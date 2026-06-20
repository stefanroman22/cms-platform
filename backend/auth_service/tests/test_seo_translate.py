# backend/auth_service/tests/test_seo_translate.py
from auth_service.translation import seo_translate


class FakeProvider:
    """Echoes UPPER(text) prefixed by target, to prove per-field translation ran."""

    def translate(self, texts, *, source, target, fmt="text"):
        return [f"{target}:{t}" for t in texts]


class FailProvider:
    def translate(self, texts, *, source, target, fmt="text"):
        raise RuntimeError("deepl down")


def test_meta_translates_prose_and_og_only():
    default = {
        "title": "Home",
        "description": "Welcome",
        "canonical": "https://x/",
        "robots": "index",
        "og": {"title": "Home", "description": "Welcome", "image": "https://x/o.png"},
        "json_ld": {"@type": "LocalBusiness", "telephone": "+31"},
    }
    out = seo_translate.translate_seo_prose(
        default, kind="meta", source="en", target="nl", provider=FakeProvider()
    )
    assert out["title"] == "nl:Home" and out["description"] == "nl:Welcome"
    assert out["og"] == {"title": "nl:Home", "description": "nl:Welcome"}  # og.image NOT translated
    # invariant fields are NOT returned (caller keeps default / site generates)
    assert "canonical" not in out and "robots" not in out and "json_ld" not in out


def test_article_translates_body_as_markdown():
    default = {
        "title": "Fades",
        "excerpt": "About fades",
        "body": "# Fades\nGreat cuts.",
        "hero_image_url": "https://x/h.png",
        "json_ld": {"@type": "Article"},
    }
    out = seo_translate.translate_seo_prose(
        default, kind="article", source="en", target="nl", provider=FakeProvider()
    )
    assert out["title"] == "nl:Fades" and out["excerpt"] == "nl:About fades"
    assert out["body"] == "nl:# Fades\nGreat cuts."
    assert "hero_image_url" not in out and "json_ld" not in out


def test_failed_translation_omits_field_never_blanks():
    default = {"title": "Home", "description": "Welcome"}
    out = seo_translate.translate_seo_prose(
        default, kind="meta", source="en", target="nl", provider=FailProvider()
    )
    # omit (so read-layer falls back to default) — NEVER write "" or None
    assert out == {} or all(v not in (None, "") for v in out.values())
    assert "title" not in out  # omitted, not blanked


def test_empty_source_fields_are_skipped():
    out = seo_translate.translate_seo_prose(
        {"title": "", "description": "Hi"},
        kind="meta",
        source="en",
        target="nl",
        provider=FakeProvider(),
    )
    assert "title" not in out and out["description"] == "nl:Hi"
