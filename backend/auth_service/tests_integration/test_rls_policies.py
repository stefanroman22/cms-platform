"""Asserts every tenant-scoped table has RLS enabled.

Service-role bypasses RLS — backend keeps working. Anon-bound queries
(future code or a typo'd refactor) become "empty result" instead of
"everyone's data". This test catches regressions where a new table
ships without RLS or someone does `ALTER TABLE … DISABLE ROW LEVEL
SECURITY`.
"""

import os

import pytest
from supabase import create_client

pytestmark = [pytest.mark.integration]

TENANT_TABLES = [
    "users",
    "sessions",
    "projects",
    "content_entries",
    "project_issues",
    "project_requests",
]


def _service_client():
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


def test_rls_enabled_on_every_tenant_table():
    sb = _service_client()
    res = sb.table("tenant_rls_status").select("tablename, rowsecurity").execute()
    by_name = {r["tablename"]: r["rowsecurity"] for r in (res.data or [])}
    missing = [t for t in TENANT_TABLES if t not in by_name]
    assert not missing, f"Tables not present in tenant_rls_status view: {missing}"
    disabled = [t for t in TENANT_TABLES if not by_name[t]]
    assert not disabled, f"RLS disabled on: {disabled}"
