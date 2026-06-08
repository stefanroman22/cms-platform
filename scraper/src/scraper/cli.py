"""Two commands:
scrape           — run a job from CLI args (manual + dry-run path)
run-pending      — claim oldest pending row from scrape_jobs, run, update.
                   This is what the systemd timer calls.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, cast

import typer
from loguru import logger
from supabase import create_client

from .categories import CURATED_CATEGORIES, DEFAULT_CATEGORIES
from .config import settings
from .geo import grid_centers
from .models import ScrapeFilters, ScrapeParams
from .pipeline import run_pipeline
from .regions import load_country
from .sinks.base import Sink
from .sinks.json_sink import JsonSink
from .sinks.supabase_sink import SupabaseSink
from .urls import InvalidMapsURLError, is_google_maps_url

app = typer.Typer(no_args_is_help=True, add_completion=False)

_DEFAULT_WEB_PRESENCE: list[str] = ["none", "social_only"]


def _build_sinks(*, dry_run: bool, supabase: bool, out_path: Path | None) -> list[Sink]:
    sinks: list[Sink] = []
    if dry_run:
        sinks.append(JsonSink(out_path or Path("./leads-dry-run.json")))
        return sinks
    if supabase:
        sinks.append(SupabaseSink())
    if not sinks:
        raise typer.BadParameter("at least one sink required (Supabase or --dry-run)")
    return sinks


def _build_sinks_single(*, dry_run: bool, supabase: bool, out_path: Path | None) -> list[Sink]:
    """Sinks for single-URL mode. Defaults differ from `_build_sinks`
    only in the dry-run output filename."""
    sinks: list[Sink] = []
    if dry_run:
        sinks.append(JsonSink(out_path or Path("./lead-single.json")))
        return sinks
    if supabase:
        sinks.append(SupabaseSink())
    if not sinks:
        raise typer.BadParameter("at least one sink required (Supabase or --dry-run)")
    return sinks


def _parse_bbox(raw: str | None) -> tuple[float, float, float, float] | None:
    """Parse '--bbox min_lat,min_lng,max_lat,max_lng' into a 4-tuple."""
    if raw is None:
        return None
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) != 4:
        raise typer.BadParameter(
            "--bbox must be 'min_lat,min_lng,max_lat,max_lng' (4 comma-separated numbers)"
        )
    try:
        box = (float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3]))
    except ValueError as exc:
        raise typer.BadParameter(f"--bbox values must be numbers: {raw!r}") from exc
    if box[0] >= box[2] or box[1] >= box[3]:
        raise typer.BadParameter(
            "--bbox must satisfy min_lat<max_lat and min_lng<max_lng "
            f"(order is min_lat,min_lng,max_lat,max_lng): {raw!r}"
        )
    return box


@app.command()
def scrape(
    category: Annotated[list[str], typer.Option("--category")] = [],  # noqa: B006
    country: Annotated[str, typer.Option("--country")] = "NL",
    city: Annotated[list[str], typer.Option("--city")] = [],  # noqa: B006 — typer reads default
    area: Annotated[list[str], typer.Option("--area")] = [],  # noqa: B006 — typer reads default
    region: Annotated[str | None, typer.Option("--region")] = None,
    bbox: Annotated[str | None, typer.Option("--bbox")] = None,
    grid_cell_km: Annotated[float, typer.Option("--grid-cell-km")] = 1.2,
    grid_zoom: Annotated[int, typer.Option("--grid-zoom")] = 16,
    max_cells: Annotated[int, typer.Option("--max-cells")] = 300,
    max: Annotated[int, typer.Option("--max")] = 120,
    language: Annotated[str, typer.Option("--language")] = "en",
    with_reviews: Annotated[bool, typer.Option("--with-reviews/--no-with-reviews")] = True,
    review_limit: Annotated[int, typer.Option("--review-limit")] = 10,
    lead_type: Annotated[str, typer.Option("--lead-type")] = "website",
    min_rating: Annotated[float | None, typer.Option("--min-rating")] = None,
    max_rating: Annotated[float | None, typer.Option("--max-rating")] = None,
    min_reviews: Annotated[int | None, typer.Option("--min-reviews")] = 3,
    max_reviews: Annotated[int | None, typer.Option("--max-reviews")] = None,
    web_presence: Annotated[list[str], typer.Option("--web-presence")] = _DEFAULT_WEB_PRESENCE,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    no_headless: Annotated[bool, typer.Option("--no-headless")] = False,
    no_supabase: Annotated[bool, typer.Option("--no-supabase")] = False,
    no_split: Annotated[bool, typer.Option("--no-split")] = False,
    out: Annotated[Path | None, typer.Option("--out")] = None,
) -> None:
    """Run a scrape with the given parameters and write to selected sinks."""
    parsed_bbox = _parse_bbox(bbox)
    grid_mode = bool(region) or parsed_bbox is not None
    params = ScrapeParams(
        category=(category[0] if category else "businesses"),
        categories=list(category) if grid_mode else [],
        country=country,
        cities=list(city),
        areas=list(area),
        max_results_per_area=max,
        language=language,
        with_reviews=with_reviews,
        review_limit=review_limit,
        lead_type=lead_type,  # type: ignore[arg-type]
        region=region,
        bbox=parsed_bbox,
        grid_cell_km=grid_cell_km,
        grid_zoom=grid_zoom,
        max_cells=max_cells,
        split_on_saturation=not no_split,
        filters=ScrapeFilters(
            min_rating=min_rating,
            max_rating=max_rating,
            min_reviews=min_reviews,
            max_reviews=max_reviews,
            web_presence=list(web_presence),  # type: ignore[arg-type]
        ),
    )
    sinks = _build_sinks(dry_run=dry_run, supabase=not no_supabase, out_path=out)
    if no_headless:
        settings.SCRAPER_HEADLESS = False

    try:
        counters = asyncio.run(run_pipeline(params, sinks))
    except ValueError as exc:
        # GridTooLargeError (cap) and the geocode-miss ValueError both surface here.
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(json.dumps(counters.__dict__))


@app.command("scrape-url")
def scrape_url(
    url: Annotated[str, typer.Argument(help="Google Maps URL of a single business.")],
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    no_headless: Annotated[bool, typer.Option("--no-headless")] = False,
    no_supabase: Annotated[bool, typer.Option("--no-supabase")] = False,
    out: Annotated[Path | None, typer.Option("--out")] = None,
    language: Annotated[str, typer.Option("--language")] = "en",
    country: Annotated[str, typer.Option("--country")] = "NL",
) -> None:
    """Scrape a single business by Google Maps URL.

    Useful for ad-hoc lead lookup and for testing the extraction pipeline
    against a known place page without running a full search.
    """
    if not is_google_maps_url(url):
        raise typer.BadParameter(
            f"not a Google Maps URL: {url!r}. Expected google.com/maps/..., "
            "maps.app.goo.gl/..., or goo.gl/maps/..."
        )

    params = ScrapeParams(
        country=country,
        language=language,
        direct_url=url,
    )
    sinks = _build_sinks_single(dry_run=dry_run, supabase=not no_supabase, out_path=out)
    if no_headless:
        settings.SCRAPER_HEADLESS = False

    try:
        counters = asyncio.run(run_pipeline(params, sinks))
    except InvalidMapsURLError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(json.dumps(counters.__dict__))


@app.command("scrape-country")
def scrape_country(
    country: Annotated[str, typer.Argument(help="ISO country code, e.g. NL")],
    deep: Annotated[bool, typer.Option("--deep")] = False,
    category: Annotated[list[str], typer.Option("--category")] = [],  # noqa: B006
    grid_cell_km: Annotated[float, typer.Option("--grid-cell-km")] = 1.2,
    limit: Annotated[int | None, typer.Option("--limit")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    max_cells_cap: Annotated[int, typer.Option("--max-cells-cap")] = 0,
    no_split: Annotated[bool, typer.Option("--no-split")] = False,
) -> None:
    """Fan a whole country out into one grid scrape job per municipality.

    Enqueues pending scrape_jobs (drained by `run-pending`). --dry-run previews
    the plan without enqueuing. --category restricts to specific categories
    (repeatable; e.g. --category restaurant); otherwise the curated set is used,
    or the full 46 with --deep. --grid-cell-km sets the tile size (smaller =
    finer = fewer per-cell results, avoiding Google's ~120 cap in dense areas)."""
    entries = load_country(country)
    if limit is not None:
        entries = entries[:limit]
    cats = list(category) if category else list(DEFAULT_CATEGORIES if deep else CURATED_CATEGORIES)

    rows: list[dict[str, Any]] = []
    total_queries = 0
    preview: list[tuple[str, int]] = []
    skipped = 0
    for e in entries:
        cells = len(list(grid_centers(*e.bbox, cell_km=grid_cell_km)))
        if max_cells_cap > 0 and cells > max_cells_cap:
            skipped += 1  # over the cap → skip, don't enqueue a job that fails at drain time
            continue
        params = ScrapeParams(
            country=country.upper(),
            region=e.name,
            bbox=e.bbox,
            categories=cats,
            grid_cell_km=grid_cell_km,
            grid_zoom=16,
            max_cells=cells,  # auto-scale: a planned muni never trips the engine guard
            split_on_saturation=not no_split,
        )
        rows.append(
            {
                "status": "pending",
                "params": params.model_dump(mode="json"),
                "triggered_by": "country-fanout",
            }
        )
        preview.append((e.name, cells))
        total_queries += cells * len(cats)

    typer.echo(
        f"{len(rows)} municipalities, {len(cats)} categories, ~{total_queries} scoped queries"
    )
    if skipped:
        typer.echo(f"  skipped {skipped} municipalities over --max-cells-cap={max_cells_cap}")
    if dry_run:
        for name, cells in preview[:20]:
            typer.echo(f"  {name}: {cells} cells")
        if len(preview) > 20:
            typer.echo(f"  ... and {len(preview) - 20} more")
        return
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        raise typer.BadParameter("SUPABASE_URL + SUPABASE_SERVICE_KEY required to enqueue")
    sb = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    sb.table("scrape_jobs").insert(rows).execute()
    typer.echo(f"enqueued {len(rows)} scrape jobs")


@app.command("run-pending")
def run_pending() -> None:
    """Claim the oldest pending scrape_jobs row and run it. Called by the
    Hetzner systemd timer."""
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        raise typer.BadParameter("SUPABASE_URL + SUPABASE_SERVICE_KEY required")

    sb = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    res = (
        sb.table("scrape_jobs")
        .select("*")
        .eq("status", "pending")
        .order("created_at")
        .limit(1)
        .execute()
    )
    rows = res.data or []
    if not rows:
        logger.info("no pending scrape jobs")
        return

    job = cast(dict[str, Any], rows[0])
    job_id = job["id"]

    # Claim by transitioning pending → running.
    sb.table("scrape_jobs").update(
        {"status": "running", "started_at": datetime.now(UTC).isoformat()}
    ).eq("id", job_id).eq("status", "pending").execute()

    try:
        params = ScrapeParams.model_validate(job["params"])
        sinks: list[Sink] = [SupabaseSink()]
        counters = asyncio.run(run_pipeline(params, sinks, scrape_job_id=job_id))
        sb.table("scrape_jobs").update(
            {
                "status": "done",
                "finished_at": datetime.now(UTC).isoformat(),
                "results_found": counters.found,
                "results_inserted": counters.inserted,
                "results_skipped": counters.skipped,
            }
        ).eq("id", job_id).execute()
    except Exception as exc:
        logger.exception("job {} failed", job_id)
        sb.table("scrape_jobs").update(
            {
                "status": "failed",
                "finished_at": datetime.now(UTC).isoformat(),
                "error": str(exc)[:2000],
            }
        ).eq("id", job_id).execute()
        raise


if __name__ == "__main__":
    app()
