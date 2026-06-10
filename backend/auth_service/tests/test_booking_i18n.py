"""Tests for the booking_i18n locale helper."""

from auth_service.services.booking_i18n import (
    COLOR_SUFFIX,
    EDITABLE_EMAIL_FIELDS,
    STRINGS,
    copy_color,
    t,
    tt,
)


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


# ---- per-field colour overrides (H2) ----


def test_color_suffix_key_convention():
    # Colours live in the same email_copy dict under "{key}__color".
    assert COLOR_SUFFIX == "__color"


def test_copy_color_returns_override_hex():
    copy = {"confirmed_heading" + COLOR_SUFFIX: "#ff8800"}
    assert copy_color(copy, "confirmed_heading", "#18181b") == "#ff8800"


def test_copy_color_falls_back_to_default_when_absent():
    assert copy_color({}, "confirmed_heading", "#123456") == "#123456"
    assert copy_color(None, "confirmed_heading", "#123456") == "#123456"


def test_copy_color_rejects_non_hex_value():
    # SEC-045: anything that is not a hex literal must fall back to the default,
    # so it can never break out of a style="color:…" attribute.
    bad = {"confirmed_heading" + COLOR_SUFFIX: 'red;"><script>alert(1)</script>'}
    assert copy_color(bad, "confirmed_heading", "#18181b") == "#18181b"


def test_color_fields_flag_marks_text_fields_only():
    by_key = {f["key"]: f for f in EDITABLE_EMAIL_FIELDS}
    # Rendered text fields accept a colour…
    assert by_key["confirmed_heading"]["color"] is True
    assert by_key["join_cta"]["color"] is True
    # …subjects are plain-text email subjects, so they do not.
    assert by_key["confirm_subject"]["color"] is False
