"""Rich-text migration for ONE version-0 project (spec §8, ADR-0010).

  python scripts/migrate_rich_text.py --project <slug> --formats <config.json>            # dry run
  python scripts/migrate_rich_text.py --project <slug> --formats <config.json> --emit-sql # + SQL + backup
  python scripts/migrate_rich_text.py --restore <backup.json> --emit-sql                  # rollback SQL

Apply the emitted SQL with the Supabase MCP execute_sql (or scripts/apply_supabase_migration.py).
Output goes to backend/scripts/.rich-text-work/ (gitignored: contains client content)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
WORK = BACKEND / "scripts" / ".rich-text-work"


def _configure_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")


def main() -> int:
    _configure_streams()
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--project")
    ap.add_argument(
        "--formats", help="JSON config: {repeaters:{svc:{field:type}}, key_values:{svc:{key:fmt}}}"
    )
    ap.add_argument("--emit-sql", action="store_true")
    ap.add_argument("--restore", help="backup JSON written by a previous --emit-sql")
    args = ap.parse_args()

    from dotenv import load_dotenv

    load_dotenv(BACKEND / ".env")
    from auth_service.services.rich_text_migration import (  # noqa: E402
        MigrationConfig,
        migration_sql,
        plan_project_migration,
        restore_sql,
        unknown_config_refs,
    )

    WORK.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    if args.restore:
        backup = json.loads(Path(args.restore).read_text("utf-8"))
        out = WORK / f"{backup['slug']}-{stamp}.restore.sql"
        out.write_text(restore_sql(backup["project_id"], backup["rows"]), "utf-8")
        print(f"restore SQL -> {out}")
        return 0

    if not args.project:
        ap.error("--project is required")
    sb = _supabase()
    proj = (
        sb.table("projects")
        .select("id, slug, default_locale, rich_text_version")
        .eq("slug", args.project)
        .single()
        .execute()
        .data
    )
    if int(proj.get("rich_text_version") or 0) >= 1:
        print(f"{args.project}: already migrated (rich_text_version=1) - nothing to do")
        return 0
    services = (
        sb.table("project_services")
        .select(
            "service_key, service_type_slug, content_entries(id, locale, draft_content, "
            "published_content, translation_meta, updated_at)"
        )
        .eq("project_id", proj["id"])
        .execute()
        .data
    ) or []
    cfg = MigrationConfig.from_dict(
        json.loads(Path(args.formats).read_text("utf-8")) if args.formats else {}
    )
    problems = unknown_config_refs(services, cfg)
    if problems:
        print(
            "config references things that don't exist:\n  " + "\n  ".join(problems),
            file=sys.stderr,
        )
        return 1
    updates = plan_project_migration(services, cfg, proj.get("default_locale") or "en")
    for u in updates:
        print(f"\n[{u.service_key} / {u.locale}] row {u.row_id}")
        for path, before, after in u.diffs:
            print(f"  {path}\n    - {before!r}\n    + {after!r}")
    print(f"\n{len(updates)} row(s) to update in {args.project}")
    if not args.emit_sql:
        print("dry run - re-run with --emit-sql to write the atomic SQL + backup")
        return 0
    touched = {u.row_id for u in updates}
    rows = [
        dict(r, service_key=s["service_key"])
        for s in services
        for r in (s.get("content_entries") or [])
        if r["id"] in touched
    ]
    backup = WORK / f"{args.project}-{stamp}.backup.json"
    backup.write_text(
        json.dumps(
            {"project_id": proj["id"], "slug": args.project, "created_at": stamp, "rows": rows},
            ensure_ascii=False,
            indent=1,
        ),
        "utf-8",
    )
    sql = WORK / f"{args.project}-{stamp}.sql"
    sql.write_text(migration_sql(proj["id"], updates), "utf-8")
    print(f"backup -> {backup}\nSQL    -> {sql}\nApply the SQL with Supabase MCP execute_sql.")
    return 0


def _supabase():
    from auth_service.services.supabase_client import get_supabase_admin

    return get_supabase_admin()


if __name__ == "__main__":
    raise SystemExit(main())
