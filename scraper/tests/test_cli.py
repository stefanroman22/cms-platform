"""CLI tests for scrape-url. Uses typer.testing.CliRunner; mocks pipeline."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from scraper.cli import app
from scraper.pipeline import Counters

runner = CliRunner()


def test_scrape_url_dry_run_builds_params_with_direct_url(tmp_path):
    out = tmp_path / "lead.json"

    captured_params = []

    async def fake_run_pipeline(params, sinks, scrape_job_id=None):
        captured_params.append(params)
        return Counters(found=1, inserted=1, skipped=0)

    with patch("scraper.cli.run_pipeline", side_effect=fake_run_pipeline):
        result = runner.invoke(
            app,
            [
                "scrape-url",
                "https://www.google.com/maps/place/Foo/data=!1s0x1:0x2",
                "--dry-run",
                "--out",
                str(out),
            ],
        )

    assert result.exit_code == 0, result.stdout
    assert len(captured_params) == 1
    assert captured_params[0].direct_url == "https://www.google.com/maps/place/Foo/data=!1s0x1:0x2"
    # Counters echoed as JSON on the last line.
    assert '"found": 1' in result.stdout
    assert '"inserted": 1' in result.stdout


def test_scrape_url_rejects_non_maps_url():
    """Rejection must happen at parse time — before the pipeline runs.
    Otherwise a guard regression could silently start a browser."""
    with patch("scraper.cli.run_pipeline") as mock_pipeline:
        result = runner.invoke(
            app,
            ["scrape-url", "https://example.com/foo", "--dry-run"],
        )
    assert result.exit_code != 0
    assert "Google Maps" in result.stdout or "Google Maps" in str(result.exception)
    mock_pipeline.assert_not_called()


def test_scrape_url_default_sink_is_supabase(tmp_path):
    """For single-URL mode, the default sink is Supabase only. Dry-run overrides this."""
    captured_sinks = []

    async def fake_run_pipeline(params, sinks, scrape_job_id=None):
        captured_sinks.append([type(s).__name__ for s in sinks])
        return Counters(found=1, inserted=1, skipped=0)

    # Not dry-run — go through the real-sink path.
    with (
        patch("scraper.cli.run_pipeline", side_effect=fake_run_pipeline),
        patch("scraper.cli.SupabaseSink") as supabase_class,
    ):
        result = runner.invoke(
            app,
            ["scrape-url", "https://www.google.com/maps/place/Foo/data=!1s0x1:0x2"],
        )

    assert result.exit_code == 0, result.stdout
    supabase_class.assert_called_once()  # Supabase sink constructed by default
