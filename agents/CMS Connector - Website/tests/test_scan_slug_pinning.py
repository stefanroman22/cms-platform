"""SEC-094 regression: the CMS Connector must pin ``manifest["project_slug"]`` to the
operator-supplied ``--slug`` in the scan (model) branch, never trust the slug echoed
back by the model.

The scan manifest is LLM output over the *untrusted* client-website source. Every
downstream privileged call builds admin/provisioning URLs from
``manifest["project_slug"]`` with the connector's admin bearer key — ``_provision``
(``POST /projects/{slug}/services``, ``PATCH /admin/projects/{slug}``) and
``_vercel_setup`` (GitHub/Vercel binding). Because the backend admin API uses the
Supabase service-role key (RLS bypassed) and the connector key is not project-scoped,
the slug string alone selects the tenant. A prompt injection in the scanned source that
makes the model emit a *different* ``project_slug`` would otherwise aim the admin-key
provisioning at another tenant (cross-tenant corruption / production-binding takeover).

The scan branch already pins ``manifest["cms_endpoint"]``; it must pin ``project_slug``
the same way.
"""

from __future__ import annotations

from unittest.mock import patch

import scan
from click.testing import CliRunner


def test_scan_branch_pins_project_slug_to_operator(tmp_path):
    """A malicious model-echoed slug must be overwritten with the operator ``--slug``
    before it reaches the privileged ``_provision`` call."""
    captured: dict = {}

    def fake_provision(manifest, api_url, api_token, out_dir=None):
        captured["provision_manifest"] = manifest

    def fake_write_outputs(manifest, output_path):
        captured["written_manifest"] = manifest
        return (tmp_path / "cms.config.json", tmp_path / "cms-provision.json")

    # The model, subverted by an injection in the scanned source, tries to retarget
    # provisioning at another tenant's slug.
    malicious_manifest = {"project_slug": "competitor-cafe", "services": []}

    runner = CliRunner()
    with (
        patch("scan.read_website_files", return_value={"index.html": "<html>hi</html>"}),
        patch("scan._call_claude", return_value=dict(malicious_manifest)),
        patch("scan.write_outputs", side_effect=fake_write_outputs),
        patch("scan._resolve_client", return_value="client@acme.com"),
        patch("scan._provision", side_effect=fake_provision),
    ):
        result = runner.invoke(
            scan.main,
            [
                "--dir",
                str(tmp_path),
                "--slug",
                "acme",
                "--provision",
                "--admin-key",
                "cmsk_test",
            ],
        )

    assert result.exit_code == 0, result.output
    # The privileged provisioning call must target the OPERATOR slug, not the model echo.
    assert captured["provision_manifest"]["project_slug"] == "acme"
    # And the written config/provision files carry the pinned slug too.
    assert captured["written_manifest"]["project_slug"] == "acme"


def test_scan_branch_pins_even_when_model_omits_slug(tmp_path):
    """If the model omits ``project_slug`` entirely, the operator slug is still set
    (so no downstream ``KeyError`` and no accidental fall-through)."""
    captured: dict = {}

    with (
        patch("scan.read_website_files", return_value={"index.html": "<html>hi</html>"}),
        patch("scan._call_claude", return_value={"services": []}),
        patch(
            "scan.write_outputs",
            return_value=(tmp_path / "cms.config.json", tmp_path / "cms-provision.json"),
        ),
        patch("scan._resolve_client", return_value="client@acme.com"),
        patch(
            "scan._provision",
            side_effect=lambda manifest, *a, **k: captured.__setitem__("m", manifest),
        ),
    ):
        result = CliRunner().invoke(
            scan.main,
            ["--dir", str(tmp_path), "--slug", "acme", "--provision", "--admin-key", "cmsk_test"],
        )

    assert result.exit_code == 0, result.output
    assert captured["m"]["project_slug"] == "acme"
