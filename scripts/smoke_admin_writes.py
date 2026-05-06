"""smoke_admin_writes.py — write-path smoke of admin endpoints.

Loads CMS_ADMIN_API_KEY from agent .env (never echoes), exercises
write endpoints with reversible payloads:

  1. POST  /admin/clients               (create throwaway user)
  2. GET   /admin/clients/lookup        (verify the user exists)
  3. GET   /admin/projects              (pick first existing project)
  4. GET   /admin/projects/{slug}       (capture current production_url)
  5. PATCH /admin/projects/{slug}       (empty body, expects updated=0)

Skips welcome-email send (real Resend call) and project create (would
leave an unowned project row). Cleanup of the created user happens
via a separate SQL step you run after this exits.

Run:
    python scripts/smoke_admin_writes.py
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ENV_PATH = Path("agents/CMS Connector - Website/.env")
BASE = "https://cms-backend-roman.vercel.app"
# Lowercased to match how the backend normalises emails on insert+lookup.
SMOKE_EMAIL = f"cms-smoke-{datetime.now(UTC).strftime('%Y%m%dt%H%M%S')}@example.com"


def load_key() -> str:
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith("CMS_ADMIN_API_KEY="):
            v = line.split("=", 1)[1].strip()
            if v:
                return v
    print("error: CMS_ADMIN_API_KEY missing/empty in agent .env", file=sys.stderr)
    sys.exit(1)


def call(
    method: str, url: str, key: str, body: dict | None = None
) -> tuple[int | None, dict | str]:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Authorization": f"Bearer {key}"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, method=method, headers=headers, data=data)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode("utf-8") or "null"
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw[:300]


def main() -> int:
    key = load_key()
    print(f"key prefix: {key[:12]}...  base: {BASE}\n")

    fails = 0

    # 1. Create throwaway client
    print(f"[1] POST /admin/clients  email={SMOKE_EMAIL}")
    status, body = call(
        "POST", f"{BASE}/admin/clients", key, {"email": SMOKE_EMAIL, "full_name": "Smoke Test"}
    )
    new_user_id = body.get("id") if isinstance(body, dict) else None
    created = isinstance(body, dict) and body.get("created", False)
    print(f"    status={status}  created={created}  id={new_user_id}")
    if status != 201:
        print(f"    body={body}")
        fails += 1

    # 2. Verify lookup hits the user
    print(f"\n[2] GET /admin/clients/lookup?email={SMOKE_EMAIL}")
    qs = urllib.parse.urlencode({"email": SMOKE_EMAIL})
    status, body = call("GET", f"{BASE}/admin/clients/lookup?{qs}", key)
    print(
        f"    status={status}  email_match={isinstance(body, dict) and body.get('email') == SMOKE_EMAIL}"
    )
    if status != 200:
        print(f"    body={body}")
        fails += 1

    # 3. List projects, pick first
    print("\n[3] GET /admin/projects (pick first slug)")
    status, body = call("GET", f"{BASE}/admin/projects", key)
    if status != 200 or not isinstance(body, list) or not body:
        print(f"    FAIL  status={status}  body={body}")
        return 1
    slug = body[0]["slug"]
    print(f"    status={status}  picked slug={slug!r}")

    # 4. Read current production_url
    print(f"\n[4] GET /admin/projects/{slug}")
    status, detail = call("GET", f"{BASE}/admin/projects/{slug}", key)
    if status != 200 or not isinstance(detail, dict):
        print(f"    FAIL  status={status}  body={detail}")
        fails += 1
        current_prod = None
    else:
        current_prod = detail.get("production_url")
        print(f"    status={status}  production_url={current_prod!r}")

    # 5. PATCH with empty body — router returns {"updated": 0} on empty payload
    # without writing anything (zero side effect).
    print(f"\n[5] PATCH /admin/projects/{slug}  body={{}} (no-op)")
    status, body = call("PATCH", f"{BASE}/admin/projects/{slug}", key, {})
    print(f"    status={status}  body={body}")
    if status != 200 or (isinstance(body, dict) and body.get("updated") not in (0, None)):
        fails += 1

    print(f"\n{5 - fails}/5 pass, {fails} fail")
    print(f"\nCleanup: smoke user email = {SMOKE_EMAIL}")
    print("Run via Supabase MCP:")
    print(f"    DELETE FROM users WHERE email = '{SMOKE_EMAIL}';")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
