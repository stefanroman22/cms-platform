"""
Tests for multilingual-aware provisioning and Vercel env-var wiring in scan.py.

Covers:
  1. Multi-locale manifest: seed order is default-first then ?locale=nl, and the
     PATCH /admin/projects/{slug} with {default_locale, locales} happens AFTER
     both seeds (verified by call-order log).
  2. Next.js framework sets NEXT_PUBLIC_CMS_ENDPOINT to the locale-less base
     {base}/content/{slug} (not appended with a locale).
  3. Single-locale manifest (flat initial_content, locales:["ro"]): one default
     seed, then PATCH with {default_locale:"ro", locales:["ro"]}; no ?locale=
     per-locale PUTs.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import scan

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _urlopen_resp():
    """Minimal context-manager mock for urllib.request.urlopen success."""
    m = MagicMock()
    m.read.return_value = b"{}"
    m.__enter__ = lambda s: s
    m.__exit__ = lambda s, *a: None
    return m


# ---------------------------------------------------------------------------
# Test 1: Multi-locale — seed order: default → non-default → PATCH locales
# ---------------------------------------------------------------------------


def test_multilang_provision_seed_order_and_locale_patch():
    """
    Multi-locale manifest (locales:["en","nl"], default "en", one text_block).
    Expected call sequence recorded in `call_log`:
      1. POST /projects/demo/services          (create)
      2. PUT  /projects/demo/services/hero     (default-en seed, no ?locale=)
      3. PUT  /projects/demo/services/hero?locale=nl  (nl seed)
      4. PATCH /admin/projects/demo            (locale set — LAST)
    """
    manifest = {
        "project_slug": "demo",
        "locales": ["en", "nl"],
        "default_locale": "en",
        "services": [
            {
                "service_type_slug": "text_block",
                "service_key": "hero",
                "label": "Hero",
                "display_order": 0,
                "page_name": "Home",
                "translatable": True,
                "initial_content": {
                    "en": {"title": "Hello"},
                    "nl": {"title": "Hallo"},
                },
            }
        ],
    }

    call_log: list[str] = []

    def fake_urlopen(req):
        call_log.append(f"{req.get_method()} {req.get_full_url()}")
        return _urlopen_resp()

    def fake_http(method, url, headers, body=None):
        call_log.append(f"{method} {url}")
        return {"updated": 1}

    with (
        patch("urllib.request.urlopen", side_effect=fake_urlopen),
        patch.object(scan, "_http", side_effect=fake_http),
    ):
        scan._provision(manifest, "http://localhost:8001", "tok")

    # Filter to the relevant entries (ignore any unrelated calls)
    post_calls = [e for e in call_log if e.startswith("POST")]
    put_calls = [e for e in call_log if e.startswith("PUT")]
    patch_calls = [e for e in call_log if e.startswith("PATCH")]

    # 1. One POST (service creation)
    assert len(post_calls) == 1
    assert "projects/demo/services" in post_calls[0]

    # 2. Two PUT calls: default (no ?locale=) before non-default (?locale=nl)
    assert len(put_calls) == 2
    assert "seed=true" in put_calls[0], "Default-locale PUT must carry ?seed=true"
    assert "?locale=" not in put_calls[0], "Default-locale PUT must NOT have ?locale= param"
    assert "seed=true" in put_calls[1], "nl PUT must carry seed=true"
    assert "locale=nl" in put_calls[1], "nl PUT must carry locale=nl"

    # 3. PATCH comes after both PUTs
    assert len(patch_calls) == 1
    post_idx = call_log.index(post_calls[0])
    put_en_idx = call_log.index(put_calls[0])
    put_nl_idx = call_log.index(put_calls[1])
    patch_idx = call_log.index(patch_calls[0])

    assert post_idx < put_en_idx < put_nl_idx < patch_idx, (
        f"Expected POST < PUT(en) < PUT(nl) < PATCH, got indices "
        f"{post_idx} < {put_en_idx} < {put_nl_idx} < {patch_idx}"
    )

    # 4. PATCH body contains default_locale and locales — verify via a second pass
    #    that also captures the body dict.
    patch_bodies: list[dict] = []

    def fake_urlopen2(req):
        return _urlopen_resp()

    def fake_http2(method, url, headers, body=None):
        if method == "PATCH":
            patch_bodies.append(body or {})
        return {"updated": 1}

    with (
        patch("urllib.request.urlopen", side_effect=fake_urlopen2),
        patch.object(scan, "_http", side_effect=fake_http2),
    ):
        scan._provision(manifest, "http://localhost:8001", "tok")

    assert len(patch_bodies) == 1
    assert patch_bodies[0].get("default_locale") == "en"
    assert patch_bodies[0].get("locales") == ["en", "nl"]


# ---------------------------------------------------------------------------
# Test 2: Next.js framework → NEXT_PUBLIC_CMS_ENDPOINT is locale-less base
# ---------------------------------------------------------------------------


def test_nextjs_framework_sets_next_public_cms_endpoint():
    """
    Manifest with framework="next" must cause _vercel_setup to set
    NEXT_PUBLIC_CMS_ENDPOINT to {base}/content/{slug} (no trailing locale).
    """
    manifest = {
        "project_slug": "portfolio",
        "framework": "next",
        "locales": ["en"],
        "default_locale": "en",
    }

    with (
        patch.object(scan, "vercel") as mock_vercel,
        patch.object(scan, "github") as mock_gh,
        patch.object(scan, "_http") as mock_http,
        patch("secrets.token_urlsafe", return_value="tok32"),
    ):
        mock_http.side_effect = lambda method, url, headers, body=None: (
            None if method == "GET" else {"updated": 5}
        )
        mock_vercel.find_project_by_repo.return_value = None
        mock_vercel.create_project.return_value = "prj_next"
        mock_gh.get_default_branch.return_value = "main"
        mock_vercel.trigger_deployment.side_effect = [
            {"id": "d1", "url": "portfolio.vercel.app"},
            {"id": "d2", "url": "portfolio-preview.vercel.app"},
        ]
        mock_gh.branch_exists.return_value = True

        scan._vercel_setup(
            manifest=manifest,
            github_repo="owner/portfolio",
            vercel_token="vtok",
            github_token="gtok",
            cms_api_url="http://localhost:8001",
            cms_api_token="ctok",
            cms_endpoint_base="https://cms.example.com",
        )

    # Collect all set_env_var calls.
    # Call signature: set_env_var(vercel_token, project_id, var_name, value, target=[...])
    # Positional: [0]=token [1]=project_id [2]=var_name [3]=value; keyword: target=
    env_calls = mock_vercel.set_env_var.call_args_list
    # Find the production call for the endpoint (var_name is at position 2)
    prod_endpoint_calls = [
        c
        for c in env_calls
        if c[0][2] == "NEXT_PUBLIC_CMS_ENDPOINT" and c[1].get("target") == ["production"]
    ]
    assert (
        len(prod_endpoint_calls) == 1
    ), f"Expected exactly one NEXT_PUBLIC_CMS_ENDPOINT production call; got {env_calls}"
    prod_url = prod_endpoint_calls[0][0][3]  # positional arg index 3: value
    assert (
        prod_url == "https://cms.example.com/content/portfolio"
    ), f"Endpoint must be locale-less base, got: {prod_url}"
    # Must NOT contain a locale suffix like /en
    assert not prod_url.endswith("/en"), "Endpoint must not end with /en"

    # Ensure VITE_ prefix is NOT used for a next.js project (var_name at position 2)
    all_var_names = [c[0][2] for c in env_calls]
    assert not any(
        name.startswith("VITE_") for name in all_var_names
    ), f"Next.js project must not use VITE_ prefix; got {all_var_names}"


# ---------------------------------------------------------------------------
# Test 3: Single-locale manifest — back-compat + locale PATCH, no ?locale= PUTs
# ---------------------------------------------------------------------------


def test_single_locale_provision_no_per_locale_puts():
    """
    Single-locale manifest (flat initial_content, locales:["ro"]).
    Expect:
      - One POST (create)
      - One PUT (default seed, no ?locale= param)
      - One PATCH with {default_locale:"ro", locales:["ro"]}
      - Zero PUT calls with ?locale=
    """
    manifest = {
        "project_slug": "acasa",
        "locales": ["ro"],
        "default_locale": "ro",
        "services": [
            {
                "service_type_slug": "text_block",
                "service_key": "hero",
                "label": "Hero",
                "display_order": 0,
                "page_name": "Home",
                "initial_content": {"title": "Bun venit"},
            }
        ],
    }

    call_log: list[str] = []
    patch_bodies: list[dict] = []

    def fake_urlopen(req):
        call_log.append(f"{req.get_method()} {req.get_full_url()}")
        return _urlopen_resp()

    def fake_http(method, url, headers, body=None):
        call_log.append(f"{method} {url}")
        if method == "PATCH":
            patch_bodies.append(body or {})
        return {"updated": 1}

    with (
        patch("urllib.request.urlopen", side_effect=fake_urlopen),
        patch.object(scan, "_http", side_effect=fake_http),
    ):
        scan._provision(manifest, "http://localhost:8001", "tok")

    post_calls = [e for e in call_log if e.startswith("POST")]
    put_calls = [e for e in call_log if e.startswith("PUT")]
    patch_calls = [e for e in call_log if e.startswith("PATCH")]

    # One POST (service creation)
    assert len(post_calls) == 1

    # One PUT (default seed) — must carry seed=true, no ?locale= param
    assert len(put_calls) == 1
    assert "seed=true" in put_calls[0], "Default-locale PUT must carry ?seed=true"
    assert "?locale=" not in put_calls[0], "Single-locale must not produce ?locale= PUTs"

    # One PATCH with correct locale payload
    assert len(patch_calls) == 1
    assert len(patch_bodies) == 1
    assert patch_bodies[0].get("default_locale") == "ro"
    assert patch_bodies[0].get("locales") == ["ro"]

    # PATCH comes after PUT (ordering guarantee)
    put_idx = call_log.index(put_calls[0])
    patch_idx = call_log.index(patch_calls[0])
    assert put_idx < patch_idx, "PATCH must come after the default seed PUT"
