"""apply_supabase_migration.py — POST a SQL file to Supabase Management API.

Avoids PowerShell quoting bugs around curl + JSON. Pure stdlib.

Required env:
    SUPABASE_PAT          Personal access token from
                          https://supabase.com/dashboard/account/tokens
    SUPABASE_PROJECT_REF  20-char project ref (subdomain of SUPABASE_URL)

Usage:
    python scripts/apply_supabase_migration.py <path-to-sql-file>
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: apply_supabase_migration.py <sql-file>", file=sys.stderr)
        return 2

    pat = os.environ.get("SUPABASE_PAT")
    ref = os.environ.get("SUPABASE_PROJECT_REF")
    if not pat or not ref:
        print(
            "error: SUPABASE_PAT and SUPABASE_PROJECT_REF must be set.",
            file=sys.stderr,
        )
        return 1

    sql_path = sys.argv[1]
    with open(sql_path, encoding="utf-8") as fh:
        sql = fh.read()

    url = f"https://api.supabase.com/v1/projects/{ref}/database/query"
    payload = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {pat}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode()
            print(f"HTTP {resp.status}")
            print(body)
            return 0
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"HTTP {e.code}", file=sys.stderr)
        print(body, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
