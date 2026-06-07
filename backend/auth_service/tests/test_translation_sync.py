from auth_service.translation.null import NullProvider
from auth_service.translation.sync import sync_locale_draft


class _UpperProvider:
    """Fake engine: 'translates' by upper-casing, and counts calls/items."""

    name = "upper"

    def __init__(self):
        self.items = []

    def translate(self, texts, *, source, target, fmt="text"):
        self.items.extend(texts)
        return [t.upper() for t in texts]


def test_first_time_translates_all_auto_leaves():
    prov = _UpperProvider()
    content, meta = sync_locale_draft(
        "text_block",
        default_content={"title": "Hi", "body": "Yo"},
        prev_default_content={},
        target_content=None,
        target_meta={},
        provider=prov,
        source_locale="en",
        target_locale="nl",
    )
    assert content == {"title": "HI", "body": "YO"}
    assert meta == {}
    assert sorted(prov.items) == ["Hi", "Yo"]


def test_unchanged_auto_leaf_is_not_retranslated():
    prov = _UpperProvider()
    content, _ = sync_locale_draft(
        "text_block",
        default_content={"title": "Hi", "body": "NEW"},
        prev_default_content={"title": "Hi", "body": "OLD"},
        target_content={"title": "bestaande", "body": "OUD"},
        target_meta={},
        provider=prov,
        source_locale="en",
        target_locale="nl",
    )
    assert content["title"] == "bestaande"  # unchanged source → kept existing translation
    assert content["body"] == "NEW".upper()  # changed source → re-translated
    assert prov.items == ["NEW"]  # only the changed leaf hit the engine


def test_manual_override_is_preserved_and_not_translated():
    prov = _UpperProvider()
    content, meta = sync_locale_draft(
        "text_block",
        default_content={"title": "Hi", "body": "CHANGED"},
        prev_default_content={"title": "Hi", "body": "OLD"},
        target_content={"title": "T", "body": "mijn eigen tekst"},
        target_meta={"body": {"src_hash": "deadbeefdeadbeef"}},
        provider=prov,
        source_locale="en",
        target_locale="nl",
    )
    assert content["body"] == "mijn eigen tekst"  # manual kept despite source change
    assert "body" not in prov.items  # engine never saw it
    assert meta == {"body": {"src_hash": "deadbeefdeadbeef"}}  # anchor preserved


def test_null_provider_mirrors_default_structure():
    content, _ = sync_locale_draft(
        "repeater",
        default_content={
            "_schema": [{"key": "t", "type": "string"}],
            "items": [{"_id": "a", "t": "Hello"}],
        },
        prev_default_content={},
        target_content=None,
        target_meta={},
        provider=NullProvider(),
        source_locale="en",
        target_locale="nl",
    )
    assert content["items"][0]["_id"] == "a"  # structure preserved
    assert content["items"][0]["t"] == "Hello"  # NullProvider echoes


def test_empty_default_content_does_not_call_provider():
    prov = _UpperProvider()
    content, meta = sync_locale_draft(
        "text_block",
        default_content={},
        prev_default_content={},
        target_content=None,
        target_meta={},
        provider=prov,
        source_locale="en",
        target_locale="nl",
    )
    assert content == {}
    assert meta == {}
    assert prov.items == []


def test_manual_override_without_target_value_falls_back_to_source():
    prov = _UpperProvider()
    content, meta = sync_locale_draft(
        "text_block",
        default_content={"title": "Hi"},
        prev_default_content={"title": "Hi"},
        target_content=None,  # no target content yet
        target_meta={"title": {"src_hash": "abc1230000000000"}},  # but marked manual
        provider=prov,
        source_locale="en",
        target_locale="nl",
    )
    assert content["title"] == "Hi"  # falls back to source text (documented bootstrap behavior)
    assert prov.items == []  # manual → never translated
    assert meta == {"title": {"src_hash": "abc1230000000000"}}
