"""Helpers for distinguishing E2E test data from real users / projects.

The integration suite + Playwright runs hit production Supabase (we
have no separate test DB right now). Without a filter, every CI run
adds rows to `public.users` and `public.projects` that show up in the
admin dashboard alongside real clients.

This module centralises the patterns so we have ONE place to update
when we add a new test fixture domain. Used by `routers/workspace.py`
to hide test data from default admin lists.

Patterns:
- Test-user emails  → `*@cms-test.dev`, `*@cms-test.local`,
                       `e2e-*@*`, `throwaway-*@*`
- Test-project slugs → `throwaway-*`, `e2e-test-project`, `playwright-*`

Anything matching is hidden from `GET /admin/clients` and
`GET /admin/projects` UNLESS the caller passes `include_test=true`.

Defense-in-depth: the dashboard filter alone hides orphan rows but
does not delete them. A pg_cron job (see
`backend/migrations/2026_05_07_pg_cron_purge_e2e_orphans.sql`) runs
daily at 04:00 UTC and hard-deletes any `throwaway-*` row older than
24 h. The 24 h margin guarantees no in-flight test run is ever
swept mid-execution. Together: fast hide + slow purge = self-healing
test-data pressure on the DB.
"""

from __future__ import annotations

import re

# Compiled once at import; kept fast — these are called per row in the
# admin list endpoints.
_TEST_EMAIL_PATTERNS = re.compile(
    r"""
    @cms-test\.(dev|local)$           # any user under our test domains
    | ^e2e-[^@]+@                     # e2e-user@…, e2e-admin@…
    | ^throwaway-[^@]+@               # throwaway-create-…@…, throwaway-…@…
    """,
    re.IGNORECASE | re.VERBOSE,
)

_TEST_SLUG_PATTERNS = re.compile(
    r"""
    ^throwaway-                       # throwaway-1778… project slugs
    | ^e2e-test-project$              # the seeded fixture project
    | ^playwright-                    # any future Playwright-created project
    """,
    re.IGNORECASE | re.VERBOSE,
)


def is_test_email(email: str | None) -> bool:
    """Return True if `email` matches a known E2E test pattern."""
    if not email:
        return False
    return bool(_TEST_EMAIL_PATTERNS.search(email))


def is_test_slug(slug: str | None) -> bool:
    """Return True if `slug` matches a known E2E test pattern."""
    if not slug:
        return False
    return bool(_TEST_SLUG_PATTERNS.search(slug))
