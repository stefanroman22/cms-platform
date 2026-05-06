"""smoke_admin_endpoints.py — read-only smoke of admin endpoints.

Loads CMS_ADMIN_API_KEY from agents/CMS Connector - Website/.env
(never echoes the value), pings each read-only admin endpoint with
Bearer auth, prints status + body byte count. Zero side effects.

Run:
    python scripts/smoke_admin_endpoints.py
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ENV_PATH = Path("agents/CMS Connector - Website/.env")
BASE = "https://cms-backend-roman.vercel.app"
EMAIL = "stefanromanpers@gmail.com"


def load_key() -> str:
    if not ENV_PATH.exists():
        print(f"error: {ENV_PATH} not found", file=sys.stderr)
        sys.exit(1)
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith("CMS_ADMIN_API_KEY="):
            return line.split("=", 1)[1].strip()
    print("error: CMS_ADMIN_API_KEY missing from .env", file=sys.stderr)
    sys.exit(1)


def probe(method: str, url: str, key: str) -> tuple[int | None, int, str]:
    req = urllib.request.Request(url, method=method, headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read()
            return resp.status, len(body), body[:120].decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        body = e.read()
        return e.code, len(body), body[:200].decode("utf-8", errors="replace")
    except Exception as e:
        return None, 0, f"ERR: {type(e).__name__}: {e}"


def main() -> int:
    key = load_key()
    print(f"key prefix: {key[:12]}...  length: {len(key)}")
    print(f"base:       {BASE}\n")

    email_q = urllib.parse.urlencode({"email": EMAIL})
    probes = [
        ("GET", f"{BASE}/admin/clients"),
        ("GET", f"{BASE}/admin/clients/lookup?{email_q}"),
        ("GET", f"{BASE}/admin/projects"),
        ("GET", f"{BASE}/admin/service-types"),
    ]

    rows = []
    for method, url in probes:
        path = url.replace(BASE, "")
        status, n, snippet = probe(method, url, key)
        rows.append((method, path, status, n, snippet))

    width = max(len(p) for _, p, *_ in rows)
    for method, path, status, n, snippet in rows:
        ok = "PASS" if status and 200 <= status < 300 else "FAIL"
        print(f"{ok}  {method:6} {path:<{width}}  {status}  {n} bytes")
        if status and status >= 400:
            print(f"      body: {snippet}")
    fails = sum(1 for r in rows if not r[2] or not (200 <= r[2] < 300))
    print(f"\n{len(rows) - fails}/{len(rows)} pass, {fails} fail")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
