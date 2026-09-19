"""
SEC-057 regression: the CMS Connector must pin the trusted CLI --slug onto the
provisioning manifest in the Claude-scan branch.

The manifest (including `project_slug`) is produced by the model from the
client website's own source files. A prompt-injected file could steer the model
to emit a different tenant's slug; because the downstream privileged consumers
(`_provision`, `_vercel_setup`) route admin-bearer writes to
`/projects/{manifest["project_slug"]}/...`, an unpinned slug is a cross-tenant
admin write. The scan branch must overwrite the model-supplied slug with the
trusted CLI value.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import scan
from click.testing import CliRunner


def _write_site(tmp_path: Path) -> Path:
    site = tmp_path / "site"
    site.mkdir()
    # One scannable source file so read_website_files() returns content
    # (INCLUDE_EXTENSIONS covers .tsx, not .html).
    (site / "page.tsx").write_text(
        "export default function Page() { return <h1>Hello</h1>; }",
        encoding="utf-8",
    )
    return site


def test_scan_branch_pins_trusted_slug_over_model_output(tmp_path):
    """A malicious model-supplied `project_slug` is overwritten by the CLI --slug."""
    site = _write_site(tmp_path)
    out = tmp_path / "out"

    # Simulate a prompt-injected manifest: the model returns another tenant's slug.
    malicious_manifest = {
        "project_slug": "victim-tenant",
        "locales": ["en"],
        "default_locale": "en",
        "services": [],
    }

    runner = CliRunner()
    with patch.object(scan, "_call_claude", return_value=dict(malicious_manifest)):
        result = runner.invoke(
            scan.main,
            [
                "--dir",
                str(site),
                "--slug",
                "legit-tenant",
                "--out",
                str(out),
            ],
        )

    assert result.exit_code == 0, result.output

    provision = json.loads((out / "cms-provision.json").read_text(encoding="utf-8"))
    assert (
        provision["project_slug"] == "legit-tenant"
    ), "scan branch must pin the trusted CLI slug, not the model-supplied one"

    config = json.loads((out / "cms.config.json").read_text(encoding="utf-8"))
    assert config["projectSlug"] == "legit-tenant"
