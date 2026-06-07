"""Tests for i18n-related instructions in the Phase-2 SYSTEM_PROMPT."""

import prompts


def _prompt() -> str:
    """Return the built prompt string, exactly as the API receives it.

    _read_learnings() silently returns "" when LEARNINGS.md has no real rules,
    so build_system_prompt() == SYSTEM_PROMPT in a clean checkout — but we call
    the builder so the test exercises the same code path as production.
    """
    return prompts.build_system_prompt()


# ---------------------------------------------------------------------------
# 1. Locale-detection instruction is present
# ---------------------------------------------------------------------------


def test_prompt_instructs_reading_i18n_routing_ts():
    assert "i18n/routing.ts" in _prompt()


def test_prompt_instructs_reading_messages_locale_json():
    assert "messages/" in _prompt()


def test_prompt_instructs_emitting_locales_field():
    p = _prompt()
    assert '"locales"' in p


def test_prompt_instructs_emitting_default_locale_field():
    p = _prompt()
    assert '"default_locale"' in p


def test_prompt_mentions_define_routing():
    assert "defineRouting" in _prompt()


def test_prompt_mentions_fallback_to_html_lang():
    assert "html lang" in _prompt() or "<html lang>" in _prompt()


def test_prompt_mentions_fallback_to_en():
    # Single-locale fallback must mention "en" as the last-resort default
    assert '"en"' in _prompt()


# ---------------------------------------------------------------------------
# 2. Manifest schema additions are documented in the Output section
# ---------------------------------------------------------------------------


def test_manifest_schema_contains_top_level_locales():
    p = _prompt()
    output_section = p[p.index("## Output") :]
    assert '"locales"' in output_section


def test_manifest_schema_contains_top_level_default_locale():
    p = _prompt()
    output_section = p[p.index("## Output") :]
    assert '"default_locale"' in output_section


def test_manifest_schema_documents_per_locale_initial_content():
    p = _prompt()
    output_section = p[p.index("## Output") :]
    # The per-locale map form must be described
    assert "per-locale" in output_section or "per locale" in output_section.lower()


def test_manifest_schema_documents_flat_single_locale_form():
    p = _prompt()
    output_section = p[p.index("## Output") :]
    assert "single-locale" in output_section or "single locale" in output_section.lower()


def test_manifest_schema_documents_translatable_flag():
    p = _prompt()
    output_section = p[p.index("## Output") :]
    assert '"translatable"' in output_section


def test_translatable_false_flat_shape_rule_present():
    """translatable:false must be documented as always using the flat single-locale form."""
    p = _prompt()
    output_section = p[p.index("## Output") :]
    assert "translatable: false" in output_section or "translatable`" in output_section
    # The key behaviour: seeded once for default locale, not per locale
    assert "seeded once" in output_section or "not duplicated per locale" in output_section


# ---------------------------------------------------------------------------
# 3. i18n exclusion is narrowed: switcher chrome stays out, content is in
# ---------------------------------------------------------------------------


def test_never_include_still_excludes_switcher_control():
    p = _prompt()
    never_section = p[p.index("## Hard rules — NEVER include") :]
    # The switcher/chrome must still be explicitly excluded
    assert "switcher" in never_section.lower() or "language-switcher" in never_section.lower()


def test_never_include_no_longer_excludes_per_locale_content():
    p = _prompt()
    never_section = p[p.index("## Hard rules — NEVER include") :]
    # The old blanket "configuration, not content" phrasing about i18n must be gone
    assert "configuration, not content" not in never_section


def test_never_include_does_not_exclude_content_generally():
    """The exclusion line must name chrome/UI only — not 'content' or 'locale toggles'."""
    p = _prompt()
    never_section = p[p.index("## Hard rules — NEVER include") : p.index("When ambiguous")]
    # "locale toggles" was the old over-broad phrase; it must be gone
    assert "locale toggles" not in never_section


def test_switcher_exclusion_says_chrome():
    p = _prompt()
    never_section = p[p.index("## Hard rules — NEVER include") : p.index("When ambiguous")]
    assert "chrome" in never_section.lower()


# ---------------------------------------------------------------------------
# 4. service_key namespace note is present
# ---------------------------------------------------------------------------


def test_service_key_rule_mentions_next_intl_namespace():
    assert "next-intl" in _prompt() or 't("<service_key>.<field>")' in _prompt()
