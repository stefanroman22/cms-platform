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


def test_scrape_region_builds_grid_mode_params(tmp_path):
    captured = []

    async def fake_run_pipeline(params, sinks, scrape_job_id=None):
        captured.append(params)
        return Counters(found=5, inserted=5, skipped=0)

    with patch("scraper.cli.run_pipeline", side_effect=fake_run_pipeline):
        result = runner.invoke(
            app,
            ["scrape", "--region", "Lelystad", "--dry-run", "--out", str(tmp_path / "o.json")],
        )

    assert result.exit_code == 0, result.stdout
    p = captured[0]
    assert p.region == "Lelystad"
    assert p.categories == []  # empty → engine uses DEFAULT_CATEGORIES
    assert p.max_results_per_area == 120
    assert p.filters.min_reviews == 3


def test_scrape_legacy_category_city_defaults(tmp_path):
    captured = []

    async def fake_run_pipeline(params, sinks, scrape_job_id=None):
        captured.append(params)
        return Counters()

    with patch("scraper.cli.run_pipeline", side_effect=fake_run_pipeline):
        result = runner.invoke(
            app,
            [
                "scrape",
                "--category",
                "restaurants",
                "--city",
                "Lelystad",
                "--dry-run",
                "--out",
                str(tmp_path / "o.json"),
            ],
        )

    assert result.exit_code == 0, result.stdout
    p = captured[0]
    assert p.category == "restaurants"  # legacy single-category preserved
    assert p.categories == []
    assert p.region is None
    assert p.max_results_per_area == 120
    assert p.filters.min_reviews == 3


def test_scrape_rejects_malformed_bbox():
    with patch("scraper.cli.run_pipeline") as mock_pipeline:
        result = runner.invoke(app, ["scrape", "--bbox", "1,2,3", "--dry-run"])
    assert result.exit_code != 0
    mock_pipeline.assert_not_called()


def test_scrape_rejects_inverted_bbox():
    # min >= max in either axis would silently tile to ~0 cells → reject early.
    with patch("scraper.cli.run_pipeline") as mock_pipeline:
        result = runner.invoke(app, ["scrape", "--bbox", "52.6,5.6,52.4,5.4", "--dry-run"])
    assert result.exit_code != 0
    mock_pipeline.assert_not_called()


def _fake_entries():
    from scraper.regions import RegionEntry

    return [
        RegionEntry(name="Alpha", country_code="NL", code="GM1", bbox=(52.0, 5.0, 52.05, 5.08)),
        RegionEntry(name="Beta", country_code="NL", code="GM2", bbox=(51.9, 4.9, 52.0, 5.0)),
    ]


def _fake_sb(captured):
    class FakeTable:
        def insert(self, rows):
            captured["rows"] = rows
            return self

        def execute(self):
            return None

    class FakeSB:
        def table(self, name):
            captured["table"] = name
            return FakeTable()

    return FakeSB()


def test_scrape_country_dry_run_plans_without_enqueue():
    with (
        patch("scraper.cli.load_country", return_value=_fake_entries()),
        patch("scraper.cli.create_client") as cc,
    ):
        result = runner.invoke(app, ["scrape-country", "NL", "--dry-run"])
    assert result.exit_code == 0, result.stdout
    assert "2 municipalities" in result.stdout
    cc.assert_not_called()


def test_scrape_country_enqueues_curated_jobs_with_autoscaled_max_cells():
    from scraper.categories import CURATED_CATEGORIES
    from scraper.geo import grid_centers

    captured = {}
    with (
        patch("scraper.cli.load_country", return_value=_fake_entries()),
        patch("scraper.cli.create_client", return_value=_fake_sb(captured)),
        patch("scraper.cli.settings") as st,
    ):
        st.SUPABASE_URL = "x"
        st.SUPABASE_SERVICE_KEY = "y"
        result = runner.invoke(app, ["scrape-country", "NL", "--limit", "1"])

    assert result.exit_code == 0, result.stdout
    assert captured["table"] == "scrape_jobs"
    assert len(captured["rows"]) == 1
    row = captured["rows"][0]
    assert row["status"] == "pending"
    assert row["triggered_by"] == "country-fanout"
    p = row["params"]
    assert p["categories"] == list(CURATED_CATEGORIES)
    assert p["region"] == "Alpha"
    assert tuple(p["bbox"]) == (52.0, 5.0, 52.05, 5.08)
    expected_cells = len(list(grid_centers(52.0, 5.0, 52.05, 5.08, cell_km=1.2)))
    assert p["max_cells"] == expected_cells  # auto-scaled, never rejects


def test_scrape_country_deep_uses_full_categories():
    from scraper.categories import DEFAULT_CATEGORIES

    captured = {}
    with (
        patch("scraper.cli.load_country", return_value=_fake_entries()),
        patch("scraper.cli.create_client", return_value=_fake_sb(captured)),
        patch("scraper.cli.settings") as st,
    ):
        st.SUPABASE_URL = "x"
        st.SUPABASE_SERVICE_KEY = "y"
        result = runner.invoke(app, ["scrape-country", "NL", "--deep", "--limit", "1"])

    assert result.exit_code == 0, result.stdout
    assert captured["rows"][0]["params"]["categories"] == list(DEFAULT_CATEGORIES)


def test_scrape_country_max_cells_cap_skips_oversized_munis():
    from scraper.geo import grid_centers
    from scraper.google_maps import _build_grid_queries
    from scraper.models import ScrapeParams

    entries = _fake_entries()
    counts = {e.name: len(list(grid_centers(*e.bbox, cell_km=1.2))) for e in entries}
    big = max(counts, key=lambda n: counts[n])
    small = min(counts, key=lambda n: counts[n])
    assert counts[big] > counts[small]  # fixture sanity: distinct sizes
    cap = counts[small]  # keeps `small` (cells == cap), skips `big` (cells > cap)

    captured = {}
    with (
        patch("scraper.cli.load_country", return_value=entries),
        patch("scraper.cli.create_client", return_value=_fake_sb(captured)),
        patch("scraper.cli.settings") as st,
    ):
        st.SUPABASE_URL = "x"
        st.SUPABASE_SERVICE_KEY = "y"
        result = runner.invoke(app, ["scrape-country", "NL", "--max-cells-cap", str(cap)])

    assert result.exit_code == 0, result.stdout
    names = [r["params"]["region"] for r in captured["rows"]]
    assert big not in names and small in names  # oversized muni skipped, not enqueued
    # Every enqueued job is auto-scaled so the engine guard never rejects it.
    for r in captured["rows"]:
        _build_grid_queries(ScrapeParams.model_validate(r["params"]))


def test_scrape_country_requires_supabase_creds():
    with (
        patch("scraper.cli.load_country", return_value=_fake_entries()),
        patch("scraper.cli.create_client") as cc,
        patch("scraper.cli.settings") as st,
    ):
        st.SUPABASE_URL = ""
        st.SUPABASE_SERVICE_KEY = ""
        result = runner.invoke(app, ["scrape-country", "NL"])
    assert result.exit_code != 0
    cc.assert_not_called()


def test_scrape_country_dry_run_real_registry_plans_342():
    # No load_country patch → exercises the real packaged nl.jsonl end-to-end.
    result = runner.invoke(app, ["scrape-country", "NL", "--dry-run"])
    assert result.exit_code == 0, result.stdout
    assert "342 municipalities" in result.stdout
    assert "scoped queries" in result.stdout  # query estimate present
    assert "more" in result.stdout  # >20 preview truncation branch


def test_scrape_country_single_category_override():
    captured = {}
    with (
        patch("scraper.cli.load_country", return_value=_fake_entries()),
        patch("scraper.cli.create_client", return_value=_fake_sb(captured)),
        patch("scraper.cli.settings") as st,
    ):
        st.SUPABASE_URL = "x"
        st.SUPABASE_SERVICE_KEY = "y"
        result = runner.invoke(
            app, ["scrape-country", "NL", "--category", "restaurant", "--limit", "1"]
        )
    assert result.exit_code == 0, result.stdout
    assert captured["rows"][0]["params"]["categories"] == ["restaurant"]


def test_scrape_country_custom_grid_cell_km_autoscales():
    from scraper.geo import grid_centers

    captured = {}
    with (
        patch("scraper.cli.load_country", return_value=_fake_entries()),
        patch("scraper.cli.create_client", return_value=_fake_sb(captured)),
        patch("scraper.cli.settings") as st,
    ):
        st.SUPABASE_URL = "x"
        st.SUPABASE_SERVICE_KEY = "y"
        result = runner.invoke(
            app,
            [
                "scrape-country",
                "NL",
                "--grid-cell-km",
                "0.8",
                "--category",
                "restaurant",
                "--limit",
                "1",
            ],
        )
    assert result.exit_code == 0, result.stdout
    p = captured["rows"][0]["params"]
    assert p["grid_cell_km"] == 0.8
    expected = len(list(grid_centers(*_fake_entries()[0].bbox, cell_km=0.8)))
    assert p["max_cells"] == expected  # auto-scaled at the custom cell size


def test_scrape_country_no_split_flag():
    captured = {}
    with (
        patch("scraper.cli.load_country", return_value=_fake_entries()),
        patch("scraper.cli.create_client", return_value=_fake_sb(captured)),
        patch("scraper.cli.settings") as st,
    ):
        st.SUPABASE_URL = "x"
        st.SUPABASE_SERVICE_KEY = "y"
        result = runner.invoke(
            app,
            ["scrape-country", "NL", "--no-split", "--category", "restaurant", "--limit", "1"],
        )
    assert result.exit_code == 0, result.stdout
    assert captured["rows"][0]["params"]["split_on_saturation"] is False


def test_scrape_country_split_on_by_default():
    captured = {}
    with (
        patch("scraper.cli.load_country", return_value=_fake_entries()),
        patch("scraper.cli.create_client", return_value=_fake_sb(captured)),
        patch("scraper.cli.settings") as st,
    ):
        st.SUPABASE_URL = "x"
        st.SUPABASE_SERVICE_KEY = "y"
        result = runner.invoke(
            app, ["scrape-country", "NL", "--category", "restaurant", "--limit", "1"]
        )
    assert result.exit_code == 0, result.stdout
    assert captured["rows"][0]["params"]["split_on_saturation"] is True


def test_scrape_region_no_split_flag(tmp_path):
    captured = []

    async def fake_run_pipeline(params, sinks, scrape_job_id=None):
        captured.append(params)
        return Counters()

    with patch("scraper.cli.run_pipeline", side_effect=fake_run_pipeline):
        result = runner.invoke(
            app,
            [
                "scrape",
                "--region",
                "Lelystad",
                "--no-split",
                "--dry-run",
                "--no-supabase",
                "--out",
                str(tmp_path / "o.json"),
            ],
        )
    assert result.exit_code == 0, result.stdout
    assert captured[0].split_on_saturation is False
