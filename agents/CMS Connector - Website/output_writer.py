"""
output_writer.py — Writes the two output files for a scanned website:
  • cms.config.json  — dropped into the client website repo
  • cms-provision.json — admin keeps this; contains full service definitions + initial content
"""

from __future__ import annotations

import json
from pathlib import Path


def write_outputs(manifest: dict, out_dir: str | Path) -> tuple[Path, Path]:
    """
    Writes cms.config.json and cms-provision.json to out_dir.
    Returns (config_path, provision_path).
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── cms.config.json ──────────────────────────────────────────────────────
    services_map = {
        svc["service_key"]: {
            "type": svc["service_type_slug"],
            "page": svc.get("page_name", "General"),
        }
        for svc in manifest.get("services", [])
    }

    config = {
        "projectSlug": manifest["project_slug"],
        "endpoint": manifest.get("cms_endpoint", "https://cms-backend-roman.vercel.app/content"),
        "services": services_map,
    }

    config_path = out_dir / "cms.config.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    # ── cms-provision.json ───────────────────────────────────────────────────
    provision_path = out_dir / "cms-provision.json"
    provision_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return config_path, provision_path
