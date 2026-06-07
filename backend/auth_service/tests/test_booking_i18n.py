"""Tests for the booking_i18n locale helper."""

from auth_service.services.booking_i18n import EDITABLE_EMAIL_FIELDS, STRINGS, t, tt


def test_t_returns_english_by_default():
    assert t("en", "confirm_subject") == STRINGS["en"]["confirm_subject"]


def test_t_none_locale_falls_back_to_en():
    assert t(None, "confirm_subject") == STRINGS["en"]["confirm_subject"]


def test_t_unknown_locale_falls_back_to_en():
    assert t("xx", "confirm_subject") == STRINGS["en"]["confirm_subject"]


def test_t_missing_key_falls_back_to_en_then_key():
    # en has the key → return it
    val = t("en", "host_new_subject", name="Alice")
    assert "Alice" in val

    # completely unknown key → returns the key itself
    assert t("en", "__no_such_key__") == "__no_such_key__"


def test_t_format_substitution():
    result = t("en", "host_new_subject", name="Bob")
    assert "Bob" in result


def test_t_reminder_subject_matches_original():
    """The English reminder subject must match the current default string."""
    assert t("en", "reminder_subject") == STRINGS["en"]["reminder_subject"]


def test_t_confirm_subject_matches_original():
    assert t("en", "confirm_subject") == STRINGS["en"]["confirm_subject"]


def test_tt_uses_override():
    assert tt({"join_cta": "Join now"}, "en", "join_cta") == "Join now"


def test_tt_falls_back_to_default():
    assert tt({}, "en", "join_cta") == STRINGS["en"]["join_cta"]
    assert tt(None, "en", "confirm_subject") == STRINGS["en"]["confirm_subject"]


def test_tt_formats_override():
    assert (
        tt({"confirmed_heading": "Booked, {name}!"}, "en", "confirmed_heading", name="Sam")
        == "Booked, Sam!"
    )


def test_editable_fields_have_known_keys():
    keys = {f["key"] for f in EDITABLE_EMAIL_FIELDS}
    assert "join_cta" in keys and "confirm_subject" in keys
    assert all(f["key"] in STRINGS["en"] for f in EDITABLE_EMAIL_FIELDS)
