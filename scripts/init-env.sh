#!/usr/bin/env bash
# scripts/init-env.sh — interactive .env scaffolder. Invoked by `make env`.
# Idempotent: safe to re-run; never overwrites an existing .env without confirmation.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

copy_or_skip() {
    local example="$1"
    local target="$2"
    if [[ -f "$target" ]]; then
        printf '  ✓ %s already exists — skipping (delete it first if you want to start over)\n' "$target"
        return 0
    fi
    cp "$example" "$target"
    printf '  + copied %s → %s\n' "$example" "$target"
}

printf '\n📦 Bootstrapping local env files\n\n'
copy_or_skip backend/.env.example      backend/.env
copy_or_skip frontend/.env.example     frontend/.env.local

printf '\n  Edit the placeholders before running `make dev`:\n'
printf '    • backend/.env     — SUPABASE_*, RESEND_*, ENVIRONMENT=development\n'
printf '    • frontend/.env.local — FASTAPI_URL=http://localhost:8001\n\n'
printf '  See docs/ENVIRONMENTS.md for the full env-var contract.\n\n'
