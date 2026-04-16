#!/usr/bin/env python3
"""
scan.py — Auto-Config Agent CLI

Scans a client website's source code with Claude and generates the CMS config
and provisioning manifest automatically.

Usage (direct):
    python backend/agent/scan.py --dir ../my-website --slug my-website

Usage (scratch-dir discovery):
    python backend/agent/scan.py --scratch-dir ../../scratch

Options:
    --dir          Path to the client website directory (required unless --scratch-dir used)
    --slug         Project slug to use in the output config (derived from dir name if omitted)
    --scratch-dir  Scan folder: lists all subdirectories and lets you pick a project
    --out          Output directory for generated files (default: same as --dir)
    --endpoint     CMS content endpoint (default: https://cms.romantechnologies.com/content)
    --provision    After generating, call the CMS admin API to create services + seed content
    --client-email Client email for provisioning (interactive if omitted with --provision)
    --api-url      CMS API base URL (default: http://localhost:8001, required with --provision)
    --api-token    Admin access token (required with --provision)
    --model        Claude model to use (default: claude-sonnet-4-6)

Requirements:
    pip install anthropic click
    export ANTHROPIC_API_KEY=sk-ant-...
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import click

from file_reader import read_website_files
from prompts import SYSTEM_PROMPT, build_user_message
from output_writer import write_outputs


DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_CMS_API = "http://localhost:8001"
DEFAULT_ENDPOINT = "https://cms.romantechnologies.com/content"

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
        p for p in scratch_dir.iterdir()
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
        "Cookie": f"access_token={api_token}",
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
    full_name = click.prompt("  Client full name (optional, press Enter to skip)", default="").strip() or None
    payload = {"email": client_email}
    if full_name:
        payload["full_name"] = full_name

    result = _http("POST", f"{base}/admin/clients", headers, payload)
    if not result:
        raise click.ClickException("Failed to create client account.")

    click.echo(f"\n  ✅ New client account created!")
    click.echo(f"     Email:    {result['email']}")
    if result.get("full_name"):
        click.echo(f"     Name:     {result['full_name']}")
    if result.get("generated_password"):
        click.echo(f"     Password: {result['generated_password']}")
        click.echo("     ⚠️  Share this password with your client. They can change it after first login.")

    return client_email


def _call_claude(model: str, project_slug: str, files: dict[str, str]) -> dict:
    """Send files to Claude and parse the returned JSON manifest."""
    try:
        import anthropic
    except ImportError:
        click.echo("Error: anthropic package not installed. Run: pip install anthropic", err=True)
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        click.echo("Error: ANTHROPIC_API_KEY environment variable not set.", err=True)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    user_message = build_user_message(project_slug, files)

    click.echo(f"  Sending {len(files)} files to Claude ({model})…")

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
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


def _provision(manifest: dict, api_url: str, api_token: str) -> None:
    """Create services + seed initial content via the CMS admin API."""
    slug = manifest["project_slug"]
    services = manifest.get("services", [])
    headers = {
        "Content-Type": "application/json",
        "Cookie": f"access_token={api_token}",
    }
    base = api_url.rstrip("/")

    created = 0
    seeded = 0

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

        # Create service
        url = f"{base}/projects/{slug}/services"
        req = urllib.request.Request(
            url, data=json.dumps(body).encode(), headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req) as resp:
                resp.read()
            created += 1
            page_tag = f"[{svc.get('page_name', 'General')}]"
            click.echo(f"  ✓ Created {page_tag} {svc['service_key']}")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            click.echo(f"  ✗ Failed to create '{svc['service_key']}': {e.code} {err_body}", err=True)
            continue

        # Seed initial content (skip email_config — destination set separately)
        if svc["service_type_slug"] == "email_config":
            continue
        initial = svc.get("initial_content")
        if not initial:
            continue

        put_url = f"{base}/projects/{slug}/services/{svc['service_key']}"
        put_req = urllib.request.Request(
            put_url, data=json.dumps({"content": initial}).encode(), headers=headers, method="PUT"
        )
        try:
            with urllib.request.urlopen(put_req) as resp:
                resp.read()
            seeded += 1
            click.echo(f"  ✓ Seeded content:  {svc['service_key']}")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            click.echo(f"  ✗ Failed to seed '{svc['service_key']}': {e.code} {err_body}", err=True)

    click.echo(f"\n  Created {created} service(s), seeded {seeded} with initial content.")


# ── CLI ───────────────────────────────────────────────────────────────────────

@click.command()
@click.option("--dir", "website_dir", default=None, help="Path to the client website directory.")
@click.option("--slug", default=None, help="Project slug (derived from directory name if omitted).")
@click.option("--scratch-dir", "scratch_dir", default=None, help="Discover projects inside this folder interactively.")
@click.option("--out", "out_dir", default=None, help="Output directory (default: same as --dir).")
@click.option("--endpoint", default=DEFAULT_ENDPOINT, show_default=True, help="CMS content endpoint URL.")
@click.option("--provision", is_flag=True, default=False, help="Call the CMS admin API to create services.")
@click.option("--client-email", "client_email", default=None, help="Client email for account lookup/creation (prompted if --provision is set).")
@click.option("--api-url", default=DEFAULT_CMS_API, show_default=True, help="CMS API base URL (used with --provision).")
@click.option("--api-token", default=None, help="Admin access_token cookie value (required with --provision).")
@click.option("--model", default=DEFAULT_MODEL, show_default=True, help="Claude model ID.")
def main(
    website_dir: str | None,
    slug: str | None,
    scratch_dir: str | None,
    out_dir: str | None,
    endpoint: str,
    provision: bool,
    client_email: str | None,
    api_url: str,
    api_token: str | None,
    model: str,
) -> None:
    """
    Auto-Config Agent: scan a client website and generate CMS configuration files.

    Run from the CMS - websites directory.

    Examples:
      # Direct mode
      python backend/agent/scan.py --dir ../../scratch/my-site --slug my-site

      # Discovery mode — pick from all projects in scratch
      python backend/agent/scan.py --scratch-dir ../../scratch

      # With provisioning and client account creation
      python backend/agent/scan.py --scratch-dir ../../scratch --provision --api-token <token>
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

    if provision and not api_token:
        raise click.ClickException("--api-token is required when using --provision.")

    output_path = Path(out_dir).resolve() if out_dir else website_path

    click.echo(f"\n🔍 Scanning: {website_path}")
    click.echo(f"   Slug:     {slug}")
    click.echo(f"   Output:   {output_path}\n")

    # ── Client account flow (before scanning, so the admin knows account state) ──
    if provision:
        client_email = _resolve_client(api_url, api_token, client_email)
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

    click.echo(f"\n✅ Done!")
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
        _provision(manifest, api_url, api_token)


if __name__ == "__main__":
    main()
