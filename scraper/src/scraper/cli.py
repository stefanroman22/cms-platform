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
from typing import Annotated

import typer
from loguru import logger
from supabase import create_client

from .config import settings
from .models import ScrapeFilters, ScrapeParams
from .pipeline import run_pipeline
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


@app.command()
def scrape(
    category: Annotated[str, typer.Option("--category")] = "businesses",
    country: Annotated[str, typer.Option("--country")] = "NL",
    city: Annotated[list[str], typer.Option("--city")] = [],  # noqa: B006 — typer reads default
    area: Annotated[list[str], typer.Option("--area")] = [],  # noqa: B006 — typer reads default
    max: Annotated[int, typer.Option("--max")] = 20,
    language: Annotated[str, typer.Option("--language")] = "en",
    with_reviews: Annotated[bool, typer.Option("--with-reviews/--no-with-reviews")] = True,
    review_limit: Annotated[int, typer.Option("--review-limit")] = 10,
    lead_type: Annotated[str, typer.Option("--lead-type")] = "website",
    min_rating: Annotated[float | None, typer.Option("--min-rating")] = None,
    max_rating: Annotated[float | None, typer.Option("--max-rating")] = None,
    min_reviews: Annotated[int | None, typer.Option("--min-reviews")] = 5,
    max_reviews: Annotated[int | None, typer.Option("--max-reviews")] = None,
    web_presence: Annotated[list[str], typer.Option("--web-presence")] = _DEFAULT_WEB_PRESENCE,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    no_headless: Annotated[bool, typer.Option("--no-headless")] = False,
    no_supabase: Annotated[bool, typer.Option("--no-supabase")] = False,
    out: Annotated[Path | None, typer.Option("--out")] = None,
) -> None:
    """Run a scrape with the given parameters and write to selected sinks."""
    params = ScrapeParams(
        category=category,
        country=country,
        cities=list(city),
        areas=list(area),
        max_results_per_area=max,
        language=language,
        with_reviews=with_reviews,
        review_limit=review_limit,
        lead_type=lead_type,  # type: ignore[arg-type]
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

    counters = asyncio.run(run_pipeline(params, sinks))
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

    job = rows[0]
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
