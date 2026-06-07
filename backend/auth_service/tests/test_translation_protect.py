from auth_service.translation.protect import protect, restore


def test_protect_masks_icu_placeholders():
    masked, tokens = protect("© {year} Acme. {count} items")
    assert "{year}" not in masked
    assert "{count}" not in masked
    assert len(tokens) == 2


def test_restore_is_exact_inverse():
    text = "Hello {name}, you have {count} messages"
    masked, tokens = protect(text)
    assert restore(masked, tokens) == text


def test_restore_after_surrounding_text_changes():
    # Simulate a translator that changed words around the (untouched) sentinels.
    masked, tokens = protect("© {year} Acme")
    # translator returns the sentinels intact but translates the rest
    translated = masked.replace("Acme", "Acme BV")
    out = restore(translated, tokens)
    assert "{year}" in out and "Acme BV" in out


def test_no_placeholders_is_passthrough():
    masked, tokens = protect("just text")
    assert masked == "just text"
    assert tokens == {}
    assert restore(masked, tokens) == "just text"


def test_repeated_placeholder_round_trips_with_distinct_sentinels():
    text = "{count} items, {count} total"
    masked, tokens = protect(text)
    assert len(tokens) == 2  # each occurrence gets its own sentinel
    assert restore(masked, tokens) == text


def test_empty_braces_are_masked_and_restored():
    masked, tokens = protect("a {} b")
    assert len(tokens) == 1
    assert "{}" not in masked
    assert restore(masked, tokens) == "a {} b"
