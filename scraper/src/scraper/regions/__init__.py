"""Per-country region registry: one <iso>.jsonl file per country, each line a
municipality/city with a precomputed bbox. Adding a country = drop in a file."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict


class RegionEntry(BaseModel):
    """One administrative unit to fan a grid scrape over. bbox order matches
    grid_centers / ScrapeParams.bbox exactly: (min_lat, min_lng, max_lat, max_lng)."""

    model_config = ConfigDict(extra="ignore")

    name: str
    country_code: str
    code: str | None = None
    bbox: tuple[float, float, float, float]
    centroid: tuple[float, float] | None = None
    population: int | None = None
    source: str | None = None


def load_country(cc: str, *, base_dir: Path | None = None) -> list[RegionEntry]:
    """Load all region entries for an ISO country code. Raises ValueError if the
    country has no registry file."""
    base = base_dir or Path(__file__).parent
    path = base / f"{cc.lower()}.jsonl"
    if not path.exists():
        raise ValueError(f"no region file for country {cc!r} ({path})")
    entries: list[RegionEntry] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line:
            entries.append(RegionEntry.model_validate_json(line))
    return entries


def list_countries(*, base_dir: Path | None = None) -> list[str]:
    """Return the ISO codes that have a registry file."""
    base = base_dir or Path(__file__).parent
    return sorted(p.stem for p in base.glob("*.jsonl"))
