"""seed_e2e.py — idempotent seed for the E2E test environment.

Creates (if missing):
  • Regular user  e2e-user@cms-test.local
  • Admin user    e2e-admin@cms-test.local
  • Project       e2e-test-project (owned by regular user)
  • 3 services    e2e_text, e2e_features, e2e_contact_form
  • allowed_origins on the project (so forms CORS works)

Re-running is safe: existing rows are detected and left alone unless
--reset is passed (which deletes + recreates the project).

Required env vars:
  SUPABASE_PAT     personal access token (sbp_*) — has DB query rights
  SUPABASE_PROJECT_REF  project ref (e.g. xeluydwpgiddbamysgyu)
  SUPABASE_URL     https://<ref>.supabase.co
  SUPABASE_SERVICE_ROLE  the new sb_secret_* key (not legacy JWT)
  E2E_USER_PASSWORD       known password to set on regular user
  E2E_ADMIN_PASSWORD      known password to set on admin user

Run:
  python scripts/seed_e2e.py
  python scripts/seed_e2e.py --reset    # nuke + recreate the project
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request

PAT = os.environ["SUPABASE_PAT"]
REF = os.environ["SUPABASE_PROJECT_REF"]
SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SERVICE_ROLE = os.environ["SUPABASE_SERVICE_ROLE"]
E2E_USER_PASSWORD = os.environ["E2E_USER_PASSWORD"]
E2E_ADMIN_PASSWORD = os.environ["E2E_ADMIN_PASSWORD"]

REGULAR_EMAIL = "e2e-user@cms-test.local"
ADMIN_EMAIL = "e2e-admin@cms-test.local"
PROJECT_SLUG = "e2e-test-project"
PROJECT_NAME = "E2E Test Project"


def _http(method: str, url: str, headers: dict, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read().decode() or "{}"
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        raise RuntimeError(f"{method} {url} → {e.code} {err}") from e


def supabase_sql(sql: str) -> list[dict]:
    """Run a SQL query via Supabase Management API."""
    return _http(
        "POST",
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        {"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"},
        {"query": sql},
    )


def auth_admin(method: str, path: str, body: dict | None = None) -> dict:
    """Hit Supabase auth admin API with the service_role key."""
    return _http(
        method,
        f"{SUPABASE_URL}/auth/v1/admin{path}",
        {
            "Authorization": f"Bearer {SERVICE_ROLE}",
            "apikey": SERVICE_ROLE,
            "Content-Type": "application/json",
        },
        body,
    )


def find_or_create_auth_user(email: str, password: str, full_name: str) -> str:
    """Returns the auth user_id. Creates if missing, resets password if exists."""
    result = _http(
        "GET",
        f"{SUPABASE_URL}/auth/v1/admin/users?filter={email}",
        {"Authorization": f"Bearer {SERVICE_ROLE}", "apikey": SERVICE_ROLE},
    )
    users = result.get("users") or []
    match = next((u for u in users if u.get("email") == email), None)
    if match:
        uid = match["id"]
        auth_admin("PUT", f"/users/{uid}", {"password": password})
        print(f"  ✓ {email} exists ({uid}) — password reset")
        return uid
    created = auth_admin(
        "POST",
        "/users",
        {
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {"full_name": full_name},
        },
    )
    uid = created["id"]
    print(f"  + created auth user {email} ({uid})")
    return uid


def upsert_public_user(uid: str, email: str, full_name: str, is_admin: bool) -> None:
    """Insert into public.users with argon2-hashed password."""
    from argon2 import PasswordHasher  # noqa: PLC0415

    hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)
    pwd = E2E_ADMIN_PASSWORD if is_admin else E2E_USER_PASSWORD
    pwd_hash = hasher.hash(pwd)
    sql = (
        "INSERT INTO users (id, email, full_name, password_hash, is_admin, is_active) "
        f"VALUES ('{uid}', '{email}', '{full_name}', '{pwd_hash}', {str(is_admin).lower()}, true) "
        "ON CONFLICT (id) DO UPDATE SET password_hash = EXCLUDED.password_hash, "
        "is_admin = EXCLUDED.is_admin, is_active = true RETURNING id, email, is_admin"
    )
    rows = supabase_sql(sql)
    print(f"  ✓ public.users upsert: {rows[0]}")


def upsert_project(owner_id: str, *, reset: bool) -> str:
    if reset:
        supabase_sql(f"DELETE FROM projects WHERE slug = '{PROJECT_SLUG}'")
        print(f"  - deleted project {PROJECT_SLUG} (--reset)")

    existing = supabase_sql(f"SELECT id FROM projects WHERE slug = '{PROJECT_SLUG}'")
    if existing:
        pid = existing[0]["id"]
        print(f"  ✓ project {PROJECT_SLUG} exists ({pid})")
        return pid
    inserted = supabase_sql(
        "INSERT INTO projects (user_id, name, slug, description, is_active, allowed_origins) "
        f"VALUES ('{owner_id}', '{PROJECT_NAME}', '{PROJECT_SLUG}', "
        "'Used by E2E tests — do not delete.', true, "
        "ARRAY['https://cms-frontend-roman.vercel.app']::text[]) "
        "RETURNING id"
    )
    pid = inserted[0]["id"]
    print(f"  + created project {PROJECT_SLUG} ({pid})")
    return pid


def upsert_seed_services(project_id: str) -> None:
    """Add the 3 seed services if missing."""
    services = [
        {
            "service_key": "e2e_text",
            "service_type_slug": "text_block",
            "label": "E2E text block",
            "display_order": 1,
            "page_name": "General",
            "content": {"title": "E2E Title", "body": "E2E Body"},
        },
        {
            "service_key": "e2e_features",
            "service_type_slug": "repeater",
            "label": "E2E features",
            "display_order": 2,
            "page_name": "General",
            "content": {
                "_schema": [
                    {"key": "label", "label": "Label", "type": "string"},
                    {"key": "detail", "label": "Detail", "type": "richtext"},
                ],
                "items": [
                    {"label": "alpha", "detail": "first"},
                    {"label": "beta", "detail": "second"},
                ],
            },
        },
        {
            "service_key": "e2e_contact_form",
            "service_type_slug": "email_config",
            "label": "E2E contact form",
            "display_order": 3,
            "page_name": "General",
            "content": {"destination_email": REGULAR_EMAIL},
        },
    ]
    for svc in services:
        row = supabase_sql(
            f"SELECT id FROM project_services WHERE project_id = '{project_id}' "
            f"AND service_key = '{svc['service_key']}'"
        )
        if row:
            sid = row[0]["id"]
            print(f"  ✓ service {svc['service_key']} exists ({sid})")
        else:
            ins = supabase_sql(
                "INSERT INTO project_services (project_id, service_type_slug, "
                "service_key, label, display_order, page_name) VALUES ("
                f"'{project_id}', '{svc['service_type_slug']}', "
                f"'{svc['service_key']}', '{svc['label']}', "
                f"{svc['display_order']}, '{svc['page_name']}') RETURNING id"
            )
            sid = ins[0]["id"]
            print(f"  + service {svc['service_key']} created ({sid})")
        ce_json = json.dumps(svc["content"]).replace("'", "''")
        supabase_sql(
            "INSERT INTO content_entries (project_service_id, draft_content, "
            f"published_content) VALUES ('{sid}', '{ce_json}'::jsonb, '{ce_json}'::jsonb) "
            "ON CONFLICT (project_service_id) DO UPDATE SET draft_content = EXCLUDED.draft_content, "
            "published_content = EXCLUDED.published_content"
        )
        print(f"    ↳ content seeded for {svc['service_key']}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--reset", action="store_true", help="delete and recreate the e2e project before seeding"
    )
    args = ap.parse_args()

    print("\n📦 Seeding E2E test data\n")
    regular_uid = find_or_create_auth_user(REGULAR_EMAIL, E2E_USER_PASSWORD, "E2E Test User")
    upsert_public_user(regular_uid, REGULAR_EMAIL, "E2E Test User", is_admin=False)
    admin_uid = find_or_create_auth_user(ADMIN_EMAIL, E2E_ADMIN_PASSWORD, "E2E Admin")
    upsert_public_user(admin_uid, ADMIN_EMAIL, "E2E Admin", is_admin=True)
    project_id = upsert_project(regular_uid, reset=args.reset)
    upsert_seed_services(project_id)
    print("\n✅ seed complete\n")


if __name__ == "__main__":
    main()
