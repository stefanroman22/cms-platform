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
from .sinks.sheets_sink import SheetsSink
from .sinks.supabase_sink import SupabaseSink

app = typer.Typer(no_args_is_help=True, add_completion=False)

_DEFAULT_WEB_PRESENCE: list[str] = ["none", "social_only"]


def _build_sinks(
    *, dry_run: bool, supabase: bool, sheet: bool, out_path: Path | None
) -> list[Sink]:
    sinks: list[Sink] = []
    if dry_run:
        sinks.append(JsonSink(out_path or Path("./leads-dry-run.json")))
        return sinks
    if supabase:
        sinks.append(SupabaseSink())
    if sheet:
        sinks.append(SheetsSink())
    if not sinks:
        raise typer.BadParameter("at least one sink required (Supabase, sheet, or --dry-run)")
    return sinks


@app.command()
def scrape(
    category: Annotated[str, typer.Argument()],
    country: Annotated[str, typer.Argument()],
    city: Annotated[list[str], typer.Option("--city")] = [],  # noqa: B006 — typer reads default
    area: Annotated[list[str], typer.Option("--area")] = [],  # noqa: B006 — typer reads default
    max: Annotated[int, typer.Option("--max")] = 120,
    language: Annotated[str, typer.Option("--language")] = "en",
    with_reviews: Annotated[bool, typer.Option("--with-reviews")] = False,
    review_limit: Annotated[int, typer.Option("--review-limit")] = 10,
    lead_type: Annotated[str, typer.Option("--lead-type")] = "website",
    min_rating: Annotated[float | None, typer.Option("--min-rating")] = None,
    max_rating: Annotated[float | None, typer.Option("--max-rating")] = None,
    min_reviews: Annotated[int | None, typer.Option("--min-reviews")] = None,
    max_reviews: Annotated[int | None, typer.Option("--max-reviews")] = None,
    web_presence: Annotated[list[str], typer.Option("--web-presence")] = _DEFAULT_WEB_PRESENCE,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    no_headless: Annotated[bool, typer.Option("--no-headless")] = False,
    no_supabase: Annotated[bool, typer.Option("--no-supabase")] = False,
    no_sheet: Annotated[bool, typer.Option("--no-sheet")] = False,
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
    sinks = _build_sinks(
        dry_run=dry_run, supabase=not no_supabase, sheet=not no_sheet, out_path=out
    )
    if no_headless:
        settings.SCRAPER_HEADLESS = False

    counters = asyncio.run(run_pipeline(params, sinks))
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
        sinks: list[Sink] = [SupabaseSink(), SheetsSink()]
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
