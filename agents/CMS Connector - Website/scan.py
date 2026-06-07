#!/usr/bin/env python3
"""
scan.py — Auto-Config Agent CLI

Scans a client website's source code with Claude and generates the CMS config
and provisioning manifest automatically.

Usage (direct):
    python "agents/CMS Connector - Website/scan.py" --dir ../my-website --slug my-website

Usage (scratch-dir discovery):
    python "agents/CMS Connector - Website/scan.py" --scratch-dir ../../scratch

Options:
    --dir          Path to the client website directory (required unless --scratch-dir used)
    --slug         Project slug to use in the output config (derived from dir name if omitted)
    --scratch-dir  Scan folder: lists all subdirectories and lets you pick a project
    --out          Output directory for generated files (default: same as --dir)
    --endpoint     CMS content endpoint (default: https://cms-backend-roman.vercel.app/content)
    --provision    After generating, call the CMS admin API to create services + seed content
    --client-email Client email for provisioning (interactive if omitted with --provision)
    --api-url      CMS API base URL (default: http://localhost:8001, required with --provision)
    --admin-key    CMS admin API key (cmsk_…); env: CMS_ADMIN_API_KEY (required with --provision)
    --model        Claude model to use (default: claude-opus-4-8 — strongest available; scan accuracy drives every downstream phase, do not downgrade)

Requirements:
    pip install anthropic click
    export ANTHROPIC_API_KEY=sk-ant-...
"""

from __future__ import annotations

import json
import os
import re
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

# Load per-agent .env (gitignored, sibling of this file). Click's
# envvar lookup happens at decoration time, so this MUST run before
# any @click.option(envvar=...) is imported. Module-top is the only
# safe location.
load_dotenv(Path(__file__).resolve().parent / ".env")

# The folder name "CMS Connector - Website" contains spaces and a hyphen so
# it cannot be a Python package. Add the script's directory to sys.path so
# the flat imports below resolve. Use append (not insert(0)) so installed
# packages (e.g. a user-installed `github` module) still win.
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.append(str(_SCRIPT_DIR))

import click  # noqa: E402
import github  # noqa: E402
import vercel  # noqa: E402
from file_reader import read_website_files  # noqa: E402
from output_writer import write_outputs  # noqa: E402
from prompts import build_system_prompt, build_user_message  # noqa: E402

DEFAULT_MODEL = "claude-opus-4-8"
# Real backend lives at cms-backend-roman.vercel.app. The historical
# romantechnologies.com domain is parked on hugedomains.com — never use it.
DEFAULT_CMS_API = "https://cms-backend-roman.vercel.app"
DEFAULT_ENDPOINT = "https://cms-backend-roman.vercel.app/content"

# Directories to skip when discovering projects in --scratch-dir
_SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", ".next", "build"}


# ── Helpers ───────────────────────────────────────────────────────────────────


def _slugify(name: str) -> str:
    """Convert a directory name to a URL-safe slug."""
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _discover_projects(scratch_dir: Path) -> list[Path]:
    """List immediate subdirectories in scratch_dir that look like client projects."""
    return sorted(
        p
        for p in scratch_dir.iterdir()
        if p.is_dir() and p.name not in _SKIP_DIRS and not p.name.startswith(".")
    )


def _pick_project(projects: list[Path]) -> Path:
    """Interactive project picker — returns the chosen directory."""
    click.echo("\nProjects found in scratch directory:\n")
    for i, p in enumerate(projects, 1):
        click.echo(f"  [{i}] {p.name}")
    click.echo()

    while True:
        raw = click.prompt("Select a project number").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(projects):
            return projects[int(raw) - 1]
        click.echo("  Invalid selection. Please enter a number from the list.")


def _http(method: str, url: str, headers: dict, body: dict | None = None) -> dict | None:
    """Minimal HTTP helper using stdlib. Returns parsed JSON or None on 404."""
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        err_body = e.read().decode()
        raise click.ClickException(f"API error {e.code}: {err_body}") from e


def _resolve_client(api_url: str, api_token: str, client_email: str | None) -> str:
    """
    Looks up the client email in the CMS. Creates an account if not found.
    Prints generated password when a new account is created.
    Returns the client's email.
    """
    base = api_url.rstrip("/")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_token}",
    }

    # Prompt if not provided
    if not client_email:
        client_email = click.prompt("\nClient email address").strip()

    click.echo(f"\n  Looking up client account: {client_email}")

    # Try lookup first
    url = f"{base}/admin/clients/lookup?email={urllib.parse.quote(client_email)}"
    existing = _http("GET", url, headers)

    if existing:
        click.echo(f"  ✓ Existing account found — {existing['email']} (id: {existing['id']})")
        return client_email

    # Create new account
    click.echo("  Account not found. Creating new client account…")
    full_name = (
        click.prompt("  Client full name (optional, press Enter to skip)", default="").strip()
        or None
    )
    payload = {"email": client_email}
    if full_name:
        payload["full_name"] = full_name

    result = _http("POST", f"{base}/admin/clients", headers, payload)
    if not result:
        raise click.ClickException("Failed to create client account.")

    click.echo("\n  ✅ New client account created!")
    click.echo(f"     Email:    {result['email']}")
    if result.get("full_name"):
        click.echo(f"     Name:     {result['full_name']}")
    if result.get("generated_password"):
        click.echo(f"     Password: {result['generated_password']}")
        click.echo(
            "     ⚠️  Share this password with your client. They can change it after first login."
        )

    return client_email


def _call_claude(model: str, project_slug: str, files: dict[str, str]) -> dict:
    """Send files to Claude and parse the returned JSON manifest.

    Prefers the `claude` CLI (covered by Max/Pro subscriptions, no extra
    billing). Falls back to the anthropic Python SDK if the CLI isn't found,
    which requires ANTHROPIC_API_KEY and bills per-token.
    """
    import shutil

    system_prompt = build_system_prompt()
    user_message = build_user_message(project_slug, files)
    combined = f"{system_prompt}\n\n{user_message}"

    claude_bin = shutil.which("claude")
    if claude_bin:
        import subprocess

        click.echo(f"  Sending {len(files)} files to Claude CLI ({model})…")
        try:
            result = subprocess.run(
                [
                    claude_bin,
                    "-p",
                    "--output-format",
                    "text",
                    "--model",
                    model,
                    "--effort",
                    "xhigh",
                ],
                input=combined,
                capture_output=True,
                text=True,
                check=True,
                encoding="utf-8",
            )
        except subprocess.CalledProcessError as e:
            click.echo(
                f"Error: claude CLI failed (exit {e.returncode}).\nstderr: {e.stderr}",
                err=True,
            )
            sys.exit(1)
        raw = result.stdout.strip()
    else:
        # Fallback: SDK + API key (pay-per-token)
        try:
            import anthropic
        except ImportError:
            click.echo(
                "Error: neither `claude` CLI nor anthropic package available. "
                "Install Claude Code (`npm i -g @anthropic-ai/claude-code`) or "
                "`pip install anthropic` + set ANTHROPIC_API_KEY.",
                err=True,
            )
            sys.exit(1)

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            click.echo(
                "Error: `claude` CLI not on PATH and ANTHROPIC_API_KEY not set. "
                "Install Claude Code for Max-plan usage or set the API key.",
                err=True,
            )
            sys.exit(1)

        client = anthropic.Anthropic(api_key=api_key)
        click.echo(f"  Sending {len(files)} files to Claude SDK ({model}, billed)…")

        # cache_control on system block hits the 5-min prompt cache on retries.
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=[
                {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}
            ],
            messages=[{"role": "user", "content": user_message}],
        )
        raw = response.content[0].text.strip()

    # Strip markdown code fences if Claude wrapped the JSON anyway
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(line for line in lines if not line.startswith("```"))

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        click.echo(f"\nError: Claude returned invalid JSON.\n{exc}\n\nRaw output:\n{raw}", err=True)
        sys.exit(1)


def _env_prefix(framework: str) -> str:
    """Return the framework-specific env-var prefix."""
    fw = (framework or "").lower()
    if "next" in fw:
        return "NEXT_PUBLIC_"
    if "vite" in fw:
        return "VITE_"
    if "astro" in fw:
        return "PUBLIC_"
    return "NEXT_PUBLIC_"


def _provision_booking(
    booking: dict,
    project_slug: str,
    api_url: str,
    api_token: str,
    out_dir: str | Path,
    framework: str = "",
) -> None:
    """Provision the booking system for a project.

    Sequence (ORDER MATTERS):
      1. POST /projects/{slug}/bookings/enable   — idempotent seed
      2. PATCH /projects/{slug}/bookings/settings
      3. POST .../bookings/resources (one per manifest resource)
      4. POST .../bookings/services  (linked to all created resource ids)
      5. PUT  .../bookings/hours
      6. Write lib/booking.ts into out_dir
    """
    base = api_url.rstrip("/")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_token}",
    }

    # Step 1: enable (idempotent seed)
    try:
        enable_req = urllib.request.Request(
            f"{base}/projects/{project_slug}/bookings/enable",
            data=b"{}",
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(enable_req) as resp:
            resp.read()
        click.echo("  ✓ Booking system enabled (seeded defaults)")
    except Exception as exc:  # noqa: BLE001
        click.echo(f"  ✗ bookings/enable failed: {exc}", err=True)

    # Step 2: settings PATCH
    public_slug = booking.get("public_slug") or project_slug
    business_name = booking.get("business_name", "")
    owner_email = booking.get("destination_email") or "stefanromanpers@gmail.com"
    settings_body = {
        "public_slug": public_slug,
        "business_name": business_name,
        "timezone": booking.get("timezone", "UTC"),
        "locale": booking.get("locale", "en"),
        "email_from_name": business_name,
        "accent_color": booking.get("accent_color", ""),
        "primary_color": booking.get("primary_color", ""),
        "calendar_provider": "none",
        "reminders_enabled": booking.get("reminders", {}).get("enabled", False),
        "reminder_offsets_min": booking.get("reminders", {}).get("offsets_min", []),
        "owner_notification_email": owner_email,
    }
    try:
        _http("PATCH", f"{base}/projects/{project_slug}/bookings/settings", headers, settings_body)
        click.echo("  ✓ Booking settings patched")
    except Exception as exc:  # noqa: BLE001
        click.echo(f"  ✗ bookings/settings failed: {exc}", err=True)

    # Step 3: create resources
    created_resource_ids: list[str] = []
    for resource in booking.get("resources", []):
        try:
            res_req = urllib.request.Request(
                f"{base}/projects/{project_slug}/bookings/resources",
                data=json.dumps(
                    {"name": resource["name"], "type": resource.get("type", "staff")}
                ).encode(),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(res_req) as resp:
                result = json.loads(resp.read().decode())
            rid = result.get("id")
            if rid:
                created_resource_ids.append(rid)
            click.echo(f"  ✓ Booking resource created: {resource['name']}")
        except Exception as exc:  # noqa: BLE001
            click.echo(
                f"  ✗ bookings/resources failed for '{resource.get('name')}': {exc}", err=True
            )

    # Step 4: create services (linked to all created resources)
    for service in booking.get("services", []):
        svc_body: dict = {
            "name": service["name"],
            "duration_min": service.get("duration_min", 60),
        }
        if created_resource_ids:
            svc_body["resource_ids"] = created_resource_ids
        try:
            svc_req = urllib.request.Request(
                f"{base}/projects/{project_slug}/bookings/services",
                data=json.dumps(svc_body).encode(),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(svc_req) as resp:
                resp.read()
            click.echo(f"  ✓ Booking service created: {service['name']}")
        except Exception as exc:  # noqa: BLE001
            click.echo(f"  ✗ bookings/services failed for '{service.get('name')}': {exc}", err=True)

    # Step 5: hours
    hours = booking.get("hours", [])
    if hours:
        try:
            hours_req = urllib.request.Request(
                f"{base}/projects/{project_slug}/bookings/hours",
                data=json.dumps({"hours": hours}).encode(),
                headers=headers,
                method="PUT",
            )
            with urllib.request.urlopen(hours_req) as resp:
                resp.read()
            click.echo(f"  ✓ Booking hours set ({len(hours)} slot(s))")
        except Exception as exc:  # noqa: BLE001
            click.echo(f"  ✗ bookings/hours failed: {exc}", err=True)

    # Step 6: generate lib/booking.ts
    _write_booking_ts(public_slug, framework, Path(out_dir))


def _write_booking_ts(slug: str, framework: str, out_dir: Path) -> None:
    """Write lib/booking.ts into out_dir using the framework-appropriate env prefix."""
    env_prefix = _env_prefix(framework)
    lib_dir = out_dir / "lib"
    lib_dir.mkdir(parents=True, exist_ok=True)
    content = f"""// Auto-generated by the CMS Connector. Headless booking client for "{slug}".
const BASE = process.env.{env_prefix}BOOKING_API_BASE!;
const SLUG = "{slug}";

export type Service = {{ id: string; name: string; duration_min: number }};
export type Slot = {{ start_utc: string }};

export async function getServices(): Promise<Service[]> {{
  const r = await fetch(`${{BASE}}/booking/${{SLUG}}/services`);
  if (!r.ok) throw new Error("booking: services failed");
  return (await r.json()).services as Service[];
}}
export async function getAvailability(serviceId: string, from: string, to: string) {{
  const r = await fetch(`${{BASE}}/booking/${{SLUG}}/availability?service_id=${{serviceId}}&from=${{from}}&to=${{to}}`);
  if (!r.ok) throw new Error("booking: availability failed");
  return (await r.json()).days as {{ date: string; slots: Slot[] }}[];
}}
export async function createBooking(input: {{
  service_id: string; start_utc: string;
  customer: {{ name: string; email: string; phone?: string; tz?: string }};
  note?: string;
}}) {{
  const r = await fetch(`${{BASE}}/booking/${{SLUG}}`, {{
    method: "POST", headers: {{ "Content-Type": "application/json" }},
    body: JSON.stringify({{ ...input, website: "" }}),
  }});
  if (!r.ok) throw new Error((await r.json().catch(() => ({{}}))).detail ?? "booking: create failed");
  return r.json() as Promise<{{ success: boolean; booking_id: string; manage_url: string; start: string; end: string }}>;
}}
export async function getManage(token: string) {{ return (await fetch(`${{BASE}}/booking/manage/${{token}}`)).json(); }}
export async function reschedule(token: string, slot_start: string) {{
  return (await fetch(`${{BASE}}/booking/manage/${{token}}/reschedule`, {{
    method: "POST", headers: {{ "Content-Type": "application/json" }}, body: JSON.stringify({{ slot_start }}),
  }})).json();
}}
export async function cancel(token: string) {{ return (await fetch(`${{BASE}}/booking/manage/${{token}}/cancel`, {{ method: "POST" }})).json(); }}
"""
    (lib_dir / "booking.ts").write_text(content, encoding="utf-8")
    click.echo(f"  ✓ lib/booking.ts written ({env_prefix}BOOKING_API_BASE)")


def _provision(
    manifest: dict, api_url: str, api_token: str, out_dir: str | Path | None = None
) -> None:
    """Create services + seed initial content via the CMS admin API.

    Clobber-safe ordering:
      1. Create all services (POST).
      2. Seed the DEFAULT locale for each service BEFORE setting the project's
         locale set — so the backend does NOT auto-translate on seed.
      3. Seed each NON-default locale (PUT …?locale=<l>) — recorded as manual
         overrides, preserving imported human translations.
      4. PATCH /admin/projects/{slug} with {default_locale, locales} LAST.
      5. If manifest has booking.detected, call _provision_booking.
    """
    slug = manifest["project_slug"]
    services = manifest.get("services", [])
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_token}",
    }
    base = api_url.rstrip("/")

    # Resolve locale set from manifest (fall back to single-locale "en")
    locales: list[str] = manifest.get("locales") or []
    default_locale: str = manifest.get("default_locale") or (locales[0] if locales else "en")
    if not locales:
        locales = [default_locale]
    non_default_locales: list[str] = [loc for loc in locales if loc != default_locale]
    is_multi_locale: bool = bool(non_default_locales)

    created = 0
    seeded = 0

    # ── Step 1: Create all services ────────────────────────────────────────────
    created_keys: set[str] = set()
    for svc in services:
        body: dict = {
            "service_type_slug": svc["service_type_slug"],
            "service_key": svc["service_key"],
            "label": svc.get("label"),
            "display_order": svc.get("display_order", 0),
            "page_name": svc.get("page_name", "General"),
        }
        if svc["service_type_slug"] == "repeater" and svc.get("item_schema"):
            body["item_schema"] = svc["item_schema"]

        url = f"{base}/projects/{slug}/services"
        req = urllib.request.Request(
            url, data=json.dumps(body).encode(), headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req) as resp:
                resp.read()
            created += 1
            created_keys.add(svc["service_key"])
            page_tag = f"[{svc.get('page_name', 'General')}]"
            click.echo(f"  ✓ Created {page_tag} {svc['service_key']}")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            click.echo(
                f"  ✗ Failed to create '{svc['service_key']}': {e.code} {err_body}", err=True
            )

    # ── Step 2: Seed DEFAULT locale for every created service ─────────────────
    # Done BEFORE setting locales on the project so the backend does NOT
    # auto-propagate default-locale content to other locales.
    for svc in services:
        if svc["service_key"] not in created_keys:
            continue
        if svc["service_type_slug"] == "email_config":
            continue
        initial = svc.get("initial_content")
        if not initial:
            continue

        # Multi-locale manifest: initial_content is a per-locale map
        if is_multi_locale and isinstance(initial, dict) and default_locale in initial:
            default_content = initial[default_locale]
        else:
            # Single-locale or flat initial_content (legacy / unchanged)
            default_content = initial

        put_url = f"{base}/projects/{slug}/services/{svc['service_key']}?seed=true"
        put_req = urllib.request.Request(
            put_url,
            data=json.dumps({"content": default_content}).encode(),
            headers=headers,
            method="PUT",
        )
        try:
            with urllib.request.urlopen(put_req) as resp:
                resp.read()
            seeded += 1
            click.echo(f"  ✓ Seeded content:  {svc['service_key']} (default: {default_locale})")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            click.echo(f"  ✗ Failed to seed '{svc['service_key']}': {e.code} {err_body}", err=True)

    # ── Step 3: Seed NON-default locales ───────────────────────────────────────
    # PUT …/services/{key}?locale=<l> — recorded as manual overrides.
    for locale in non_default_locales:
        for svc in services:
            if svc["service_key"] not in created_keys:
                continue
            if svc["service_type_slug"] == "email_config":
                continue
            # Skip non-translatable services for per-locale seeding
            if not svc.get("translatable", True):
                continue
            initial = svc.get("initial_content")
            if not initial or not isinstance(initial, dict):
                continue
            locale_content = initial.get(locale)
            if not locale_content:
                continue

            put_url = (
                f"{base}/projects/{slug}/services/{svc['service_key']}?seed=true&locale={locale}"
            )
            put_req = urllib.request.Request(
                put_url,
                data=json.dumps({"content": locale_content}).encode(),
                headers=headers,
                method="PUT",
            )
            try:
                with urllib.request.urlopen(put_req) as resp:
                    resp.read()
                seeded += 1
                click.echo(f"  ✓ Seeded content:  {svc['service_key']} (locale: {locale})")
            except urllib.error.HTTPError as e:
                err_body = e.read().decode()
                click.echo(
                    f"  ✗ Failed to seed '{svc['service_key']}' locale={locale}: "
                    f"{e.code} {err_body}",
                    err=True,
                )

    # ── Step 4: Set project locale set LAST (plain column write, no translate) ─
    _http(
        "PATCH",
        f"{base}/admin/projects/{slug}",
        headers,
        {"default_locale": default_locale, "locales": locales},
    )
    click.echo(f"  ✓ Locale set committed: default={default_locale}, locales={locales}")

    click.echo(f"\n  Created {created} service(s), seeded {seeded} with initial content.")

    # ── Step 5: Booking provisioning (gated on booking.detected) ──────────────
    booking = manifest.get("booking", {})
    if booking.get("detected") and out_dir is not None:
        click.echo("\n  Provisioning booking system…")
        _provision_booking(
            booking,
            slug,
            api_url,
            api_token,
            out_dir,
            framework=manifest.get("framework", ""),
        )


def _vercel_setup(
    manifest: dict,
    github_repo: str,
    vercel_token: str,
    github_token: str,
    cms_api_url: str,
    cms_api_token: str,
    cms_endpoint_base: str,
) -> None:
    """Creates/locates Vercel project, sets env vars, creates preview branch,
    triggers prod + preview deploys, saves URLs/token to the CMS project row.
    Idempotent: safe to re-run — reuses existing preview_token from CMS.
    """
    slug = manifest["project_slug"]
    click.echo(f"\n🚀 Vercel setup for {github_repo}…")

    base = cms_api_url.rstrip("/")
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {cms_api_token}"}

    # 0. Fetch existing project row from CMS to check for reusable state (idempotency)
    existing = _http("GET", f"{base}/admin/projects/{slug}", headers) or {}

    if not existing:
        create = _http(
            "POST",
            f"{base}/admin/projects",
            headers,
            {
                "slug": slug,
                "name": manifest.get("project_name", slug),
                "owner_email": manifest.get("developer_email", "stefanromanpers@gmail.com"),
            },
        )
        if create:
            existing = create
            click.echo(f"  ✓ Created CMS project row: {slug}")

    # 1. Reuse preview_token if present, else generate a fresh one
    preview_token = existing.get("preview_token") or secrets.token_urlsafe(32)

    # 2. Find or create Vercel project — use Vercel's productionBranch if we
    #    find an existing project (authoritative source), else fall back to
    #    GitHub's default_branch.
    found = vercel.find_project_by_repo(vercel_token, github_repo)
    if found:
        project_id = found["id"]
        prod_branch = found.get("production_branch") or github.get_default_branch(
            github_token, github_repo
        )
        click.echo(f"  ✓ Found existing Vercel project: {project_id} (prod branch: {prod_branch})")
    else:
        project_id = vercel.create_project(vercel_token, name=slug, github_repo=github_repo)
        prod_branch = github.get_default_branch(github_token, github_repo)
        click.echo(f"  ✓ Created Vercel project: {project_id} (prod branch: {prod_branch})")

    # Disable Vercel Authentication on every project we touch. Idempotent.
    # Doing this BEFORE env vars + deployment trigger means the very first
    # deployment is already public — no client ever sees the SSO gate.
    vercel.disable_deployment_protection(vercel_token, project_id)
    click.echo("  ✓ Vercel deployment protection disabled (public preview/production)")

    # 3. Set env vars (upserts).
    #    Framework-specific prefix: Next.js → NEXT_PUBLIC_*, Vite → VITE_*,
    #    Astro → PUBLIC_* (others fall back to NEXT_PUBLIC_*).
    #    The production var is the locale-less base ({base}/content/{slug})
    #    so the generated site's i18n/request.ts can append /{locale} itself.
    framework = manifest.get("framework", "")
    env_prefix = _env_prefix(framework)

    endpoint_prod = f"{cms_endpoint_base}/content/{slug}"
    endpoint_preview = f"{cms_endpoint_base}/content/{slug}/draft"
    endpoint_var = f"{env_prefix}CMS_ENDPOINT"
    preview_token_var = f"{env_prefix}CMS_PREVIEW_TOKEN"

    vercel.set_env_var(vercel_token, project_id, endpoint_var, endpoint_prod, target=["production"])
    vercel.set_env_var(vercel_token, project_id, endpoint_var, endpoint_preview, target=["preview"])
    vercel.set_env_var(
        vercel_token, project_id, preview_token_var, preview_token, target=["preview"]
    )

    # Set booking API base when booking is detected
    if manifest.get("booking", {}).get("detected"):
        booking_var = f"{env_prefix}BOOKING_API_BASE"
        booking_base = cms_endpoint_base
        vercel.set_env_var(
            vercel_token, project_id, booking_var, booking_base, target=["production"]
        )
        vercel.set_env_var(vercel_token, project_id, booking_var, booking_base, target=["preview"])
        click.echo(f"  ✓ {booking_var} set (production + preview)")

    click.echo(f"  ✓ Env vars set (production + preview, {env_prefix} prefix)")

    # 4. Create cms-preview branch if missing (branched from production branch)
    if not github.branch_exists(github_token, github_repo, "cms-preview"):
        github.create_branch(github_token, github_repo, "cms-preview", from_branch=prod_branch)
        click.echo(f"  ✓ Created cms-preview branch (from {prod_branch})")
    else:
        click.echo("  ✓ cms-preview branch already exists")

    # 5. Trigger deployments (production branch → production target)
    prod = vercel.trigger_deployment(
        vercel_token, project_id, github_repo, prod_branch, production_branch=prod_branch
    )
    preview = vercel.trigger_deployment(
        vercel_token, project_id, github_repo, "cms-preview", production_branch=prod_branch
    )

    production_url = f"https://{prod['url']}" if prod.get("url") else None
    preview_url = f"https://{preview['url']}" if preview.get("url") else None
    click.echo(
        f"  ✓ Deployments triggered\n    prod:    {production_url}\n    preview: {preview_url}"
    )

    # 6. Save to CMS project row via admin PATCH (base + headers defined at top).
    #    Fold locale fields in so a Vercel-only run still sets default_locale/locales.
    #    (When _provision already ran, this is a no-op overwrite of the same values.)
    locales: list[str] = manifest.get("locales") or []
    default_locale: str = manifest.get("default_locale") or (locales[0] if locales else "en")
    if not locales:
        locales = [default_locale]
    _http(
        "PATCH",
        f"{base}/admin/projects/{slug}",
        headers,
        {
            "github_repo": github_repo,
            "production_branch": prod_branch,
            "vercel_project_id": project_id,
            "production_url": production_url,
            "preview_url": preview_url,
            "preview_token": preview_token,
            "default_locale": default_locale,
            "locales": locales,
        },
    )
    click.echo(f"  ✓ Saved Vercel metadata to CMS project row (prod branch: {prod_branch})")


# ── CLI ───────────────────────────────────────────────────────────────────────


@click.command()
@click.option("--dir", "website_dir", default=None, help="Path to the client website directory.")
@click.option("--slug", default=None, help="Project slug (derived from directory name if omitted).")
@click.option(
    "--scratch-dir",
    "scratch_dir",
    default=None,
    help="Discover projects inside this folder interactively.",
)
@click.option("--out", "out_dir", default=None, help="Output directory (default: same as --dir).")
@click.option(
    "--endpoint", default=DEFAULT_ENDPOINT, show_default=True, help="CMS content endpoint URL."
)
@click.option(
    "--provision", is_flag=True, default=False, help="Call the CMS admin API to create services."
)
@click.option(
    "--client-email",
    "client_email",
    default=None,
    help="Client email for account lookup/creation (prompted if --provision is set).",
)
@click.option(
    "--api-url",
    default=DEFAULT_CMS_API,
    show_default=True,
    help="CMS API base URL (used with --provision).",
)
@click.option(
    "--admin-key",
    "admin_key",
    default=None,
    envvar="CMS_ADMIN_API_KEY",
    help="CMS admin API key (cmsk_…). env: CMS_ADMIN_API_KEY.",
)
@click.option("--model", default=DEFAULT_MODEL, show_default=True, help="Claude model ID.")
@click.option(
    "--github-repo",
    "github_repo",
    default=None,
    help="GitHub repo (OWNER/NAME) — enables Vercel setup.",
)
@click.option(
    "--vercel-token",
    "vercel_token",
    default=None,
    envvar="VERCEL_TOKEN",
    help="Vercel API token (env: VERCEL_TOKEN).",
)
@click.option(
    "--github-token",
    "github_token",
    default=None,
    envvar="GITHUB_TOKEN",
    help="GitHub API token (env: GITHUB_TOKEN).",
)
@click.option(
    "--skip-vercel",
    is_flag=True,
    default=False,
    help="Skip Vercel setup even if --github-repo is given.",
)
def main(
    website_dir: str | None,
    slug: str | None,
    scratch_dir: str | None,
    out_dir: str | None,
    endpoint: str,
    provision: bool,
    client_email: str | None,
    api_url: str,
    admin_key: str | None,
    model: str,
    github_repo: str | None,
    vercel_token: str | None,
    github_token: str | None,
    skip_vercel: bool,
) -> None:
    """
    Auto-Config Agent: scan a client website and generate CMS configuration files.

    Run from the CMS - websites directory.

    Examples:
      # Direct mode
      python "agents/CMS Connector - Website/scan.py" --dir ../../scratch/my-site --slug my-site

      # Discovery mode — pick from all projects in scratch
      python "agents/CMS Connector - Website/scan.py" --scratch-dir ../../scratch

      # With provisioning and client account creation
      python "agents/CMS Connector - Website/scan.py" --scratch-dir ../../scratch --provision --admin-key <cmsk_…>
    """
    # ── Resolve website directory ─────────────────────────────────────────────
    if scratch_dir:
        scratch_path = Path(scratch_dir).resolve()
        if not scratch_path.is_dir():
            raise click.ClickException(f"'{scratch_dir}' is not a directory.")
        projects = _discover_projects(scratch_path)
        if not projects:
            raise click.ClickException(f"No project directories found in '{scratch_dir}'.")
        chosen = _pick_project(projects)
        website_path = chosen
    elif website_dir:
        website_path = Path(website_dir).resolve()
        if not website_path.is_dir():
            raise click.ClickException(f"'{website_dir}' is not a directory.")
    else:
        raise click.ClickException("Provide either --dir or --scratch-dir.")

    # ── Derive slug ───────────────────────────────────────────────────────────
    if not slug:
        slug = _slugify(website_path.name)
        click.echo(f"  Auto-derived slug: {slug}")

    if provision and not admin_key:
        raise click.ClickException("--admin-key is required when using --provision.")

    output_path = Path(out_dir).resolve() if out_dir else website_path

    click.echo(f"\n🔍 Scanning: {website_path}")
    click.echo(f"   Slug:     {slug}")
    click.echo(f"   Output:   {output_path}\n")

    # ── Client account flow (before scanning, so the admin knows account state) ──
    if provision:
        client_email = _resolve_client(api_url, admin_key, client_email)
        click.echo()

    # ── Read source files ─────────────────────────────────────────────────────
    files = read_website_files(website_path)
    if not files:
        raise click.ClickException("No source files found. Check the --dir path.")
    click.echo(f"  Found {len(files)} source file(s) to analyse.")

    # ── Call Claude ───────────────────────────────────────────────────────────
    manifest = _call_claude(model, slug, files)
    manifest["cms_endpoint"] = endpoint

    # ── Write output files ────────────────────────────────────────────────────
    config_path, provision_path = write_outputs(manifest, output_path)

    click.echo("\n✅ Done!")
    click.echo(f"   cms.config.json    → {config_path}")
    click.echo(f"   cms-provision.json → {provision_path}")

    # ── Print summary grouped by page ─────────────────────────────────────────
    services = manifest.get("services", [])
    pages: dict[str, list[dict]] = {}
    for svc in services:
        page = svc.get("page_name", "General")
        pages.setdefault(page, []).append(svc)

    click.echo(f"\n   Detected {len(services)} service(s) across {len(pages)} page(s):\n")
    for page, svcs in pages.items():
        click.echo(f"   [{page}]")
        for svc in svcs:
            schema_note = ""
            if svc["service_type_slug"] == "repeater" and svc.get("item_schema"):
                fields = ", ".join(f["key"] for f in svc["item_schema"])
                schema_note = f"  [{fields}]"
            click.echo(f"     • {svc['service_key']:25s} ({svc['service_type_slug']}){schema_note}")
        click.echo()

    # ── Optional provisioning ─────────────────────────────────────────────────
    if provision:
        click.echo(f"🚀 Provisioning services via {api_url}…")
        _provision(manifest, api_url, admin_key, out_dir=output_path)

    # ── Optional Vercel setup ──────────────────────────────────────────────────
    if github_repo and not skip_vercel:
        if not vercel_token or not github_token:
            raise click.ClickException(
                "--vercel-token and --github-token (or env vars) required for Vercel setup."
            )
        if not admin_key:
            raise click.ClickException(
                "--admin-key required for Vercel setup (used to PATCH the project row)."
            )

        # Derive CMS endpoint base from the existing --endpoint (strip any /content suffix)
        endpoint_base = endpoint.rstrip("/").rsplit("/content", 1)[0]
        _vercel_setup(
            manifest=manifest,
            github_repo=github_repo,
            vercel_token=vercel_token,
            github_token=github_token,
            cms_api_url=api_url,
            cms_api_token=admin_key,
            cms_endpoint_base=endpoint_base,
        )


if __name__ == "__main__":
    main()
