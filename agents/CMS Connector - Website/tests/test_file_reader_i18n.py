"""
Tests for i18n / translation-file awareness in file_reader.py.
Constructs temp directory trees the same way other tests in this suite work:
using tmp_path (pytest built-in) and writing real files.
"""

from __future__ import annotations

from pathlib import Path

from file_reader import _is_locale_json, _priority_score, read_website_files

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_tree(tmp_path: Path, files: dict[str, str]) -> Path:
    """Create files described by {relative_path: content} under tmp_path."""
    for rel, content in files.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# Unit tests for _is_locale_json
# ---------------------------------------------------------------------------


def test_locale_json_in_messages_dir():
    assert _is_locale_json("messages/en.json") is True


def test_locale_json_nl_in_messages_dir():
    assert _is_locale_json("messages/nl.json") is True


def test_locale_json_en_gb_in_messages_dir():
    assert _is_locale_json("messages/en-GB.json") is True


def test_locale_json_bare_locale_filename():
    """A bare locale-code filename at any depth should be accepted."""
    assert _is_locale_json("src/i18n/en.json") is True
    assert _is_locale_json("en.json") is True


def test_locale_json_in_locales_dir():
    assert _is_locale_json("locales/nl.json") is True


def test_locale_json_in_i18n_dir():
    # Not a locale-code filename but sits inside i18n/
    assert _is_locale_json("i18n/config.json") is True


def test_package_json_not_locale():
    assert _is_locale_json("package.json") is False


def test_package_lock_not_locale():
    assert _is_locale_json("package-lock.json") is False


def test_tsconfig_not_locale():
    assert _is_locale_json("tsconfig.json") is False


def test_tsconfig_base_not_locale():
    assert _is_locale_json("tsconfig.base.json") is False


def test_generic_config_json_not_locale():
    """A random config JSON in a non-i18n dir should not be a locale file."""
    assert _is_locale_json("config/settings.json") is False


# ---------------------------------------------------------------------------
# Unit tests for _priority_score
# ---------------------------------------------------------------------------


def test_score_messages_en_json_positive():
    assert _priority_score("messages/en.json") > 0


def test_score_messages_nl_json_positive():
    assert _priority_score("messages/nl.json") > 0


def test_score_i18n_routing_ts_high():
    score = _priority_score("i18n/routing.ts")
    assert score >= 3  # i18n segment boost applies


def test_score_locale_route_segment_boosted():
    score = _priority_score("app/[locale]/page.tsx")
    assert score >= 2  # [locale] boost applies


def test_score_package_json_negative():
    assert _priority_score("package.json") < 0


def test_score_package_lock_json_negative():
    assert _priority_score("package-lock.json") < 0


# ---------------------------------------------------------------------------
# Integration tests via read_website_files
# ---------------------------------------------------------------------------


def test_messages_catalogs_included(tmp_path: Path):
    """messages/en.json and messages/nl.json must appear in the result."""
    _make_tree(
        tmp_path,
        {
            "messages/en.json": '{"hello": "Hello"}',
            "messages/nl.json": '{"hello": "Hallo"}',
            "app/page.tsx": "export default function Page() { return <main/>; }",
        },
    )
    result = read_website_files(tmp_path)
    keys = set(result.keys())
    assert any("en.json" in k for k in keys), f"en.json missing from {keys}"
    assert any("nl.json" in k for k in keys), f"nl.json missing from {keys}"


def test_i18n_routing_ts_included(tmp_path: Path):
    """i18n/routing.ts must be selected."""
    _make_tree(
        tmp_path,
        {
            "i18n/routing.ts": "export const locales = ['en', 'nl'];",
            "app/page.tsx": "export default function Page() { return <main/>; }",
        },
    )
    result = read_website_files(tmp_path)
    keys = set(result.keys())
    assert any("routing.ts" in k for k in keys), f"routing.ts missing from {keys}"


def test_package_json_excluded(tmp_path: Path):
    """package.json must NOT appear in the results."""
    _make_tree(
        tmp_path,
        {
            "package.json": '{"name": "my-app", "version": "1.0.0"}',
            "app/page.tsx": "export default function Page() { return <main/>; }",
        },
    )
    result = read_website_files(tmp_path)
    keys = set(result.keys())
    # package.json should be filtered out entirely
    assert not any(k.endswith("package.json") for k in keys), f"package.json leaked into {keys}"


def test_package_lock_json_excluded(tmp_path: Path):
    """package-lock.json must NOT appear in the results."""
    _make_tree(
        tmp_path,
        {
            "package-lock.json": '{"lockfileVersion": 3}',
            "app/page.tsx": "export default function Page() { return <main/>; }",
        },
    )
    result = read_website_files(tmp_path)
    keys = set(result.keys())
    assert not any(
        k.endswith("package-lock.json") for k in keys
    ), f"package-lock.json leaked into {keys}"


def test_locale_route_tsx_still_selected(tmp_path: Path):
    """app/[locale]/page.tsx (existing tsx) must still be selected — regression check."""
    _make_tree(
        tmp_path,
        {
            "app/[locale]/page.tsx": "export default function LocalePage() { return <div/>; }",
        },
    )
    result = read_website_files(tmp_path)
    keys = set(result.keys())
    assert any(
        "[locale]" in k and k.endswith("page.tsx") for k in keys
    ), f"[locale]/page.tsx missing from {keys}"


def test_messages_rank_above_package_json(tmp_path: Path):
    """
    Even when both are present, locale catalogs must rank higher than
    noisy JSON files (which are excluded entirely, so they should not appear).
    """
    _make_tree(
        tmp_path,
        {
            "messages/en.json": '{"title": "Home"}',
            "package.json": '{"name": "site"}',
            "app/page.tsx": "export default function Page() {}",
        },
    )
    result = read_website_files(tmp_path)
    keys = list(result.keys())
    assert any("en.json" in k for k in keys), "en.json should be present"
    assert not any(k.endswith("package.json") for k in keys), "package.json should be absent"


def test_tsconfig_json_excluded(tmp_path: Path):
    """tsconfig.json must not appear in results."""
    _make_tree(
        tmp_path,
        {
            "tsconfig.json": '{"compilerOptions": {}}',
            "app/page.tsx": "export default function Page() {}",
        },
    )
    result = read_website_files(tmp_path)
    keys = set(result.keys())
    assert not any(k.endswith("tsconfig.json") for k in keys)
