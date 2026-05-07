"""Unit tests for `services.test_data` patterns.

Adding a new E2E fixture domain? Mirror it here so the dashboard
filter doesn't silently drop a real user / project that happens to
look test-y.
"""

from auth_service.services.test_data import is_test_email, is_test_slug

# ── Email patterns ────────────────────────────────────────────────────────


def test_is_test_email_cms_test_dev():
    assert is_test_email("e2e-user@cms-test.dev") is True
    assert is_test_email("anything@cms-test.dev") is True
    assert is_test_email("ANYONE@CMS-TEST.DEV") is True


def test_is_test_email_cms_test_local():
    assert is_test_email("e2e-admin@cms-test.local") is True


def test_is_test_email_e2e_prefix():
    """`e2e-foo@gmail.com` should match — operator may use a real
    inbox for an E2E account, but the `e2e-` prefix is the fingerprint."""
    assert is_test_email("e2e-user@gmail.com") is True


def test_is_test_email_throwaway_prefix():
    assert is_test_email("throwaway-create-1778@cms-test.dev") is True
    assert is_test_email("throwaway-anything@example.com") is True


def test_is_test_email_real_user():
    assert is_test_email("stefanromanpers@gmail.com") is False
    assert is_test_email("george.nadejde@hotmail.com") is False
    assert is_test_email("client@laurianduma.com") is False


def test_is_test_email_none_or_empty():
    assert is_test_email(None) is False
    assert is_test_email("") is False


# ── Slug patterns ─────────────────────────────────────────────────────────


def test_is_test_slug_throwaway():
    assert is_test_slug("throwaway-1778176866") is True
    assert is_test_slug("throwaway-anything") is True


def test_is_test_slug_e2e_test_project():
    assert is_test_slug("e2e-test-project") is True


def test_is_test_slug_playwright_prefix():
    """Reserved for future Playwright-driven project creation tests."""
    assert is_test_slug("playwright-foo") is True


def test_is_test_slug_real_project():
    assert is_test_slug("it-global-services") is False
    assert is_test_slug("laurian-duma-portfolio") is False
    assert is_test_slug("roman-technologies-website") is False


def test_is_test_slug_none_or_empty():
    assert is_test_slug(None) is False
    assert is_test_slug("") is False
