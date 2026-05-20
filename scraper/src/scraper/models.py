"""Pydantic v2 schemas — single source of truth shared by CLI, pipeline,
sinks and the FastAPI admin layer (via JSON serialisation through
scrape_jobs.params)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

LeadType = Literal["website", "automation", "both"]
WebPresence = Literal["none", "social_only", "has_website", "unknown"]


class ScrapeFilters(BaseModel):
    """All optional, off by default. The default web_presence list keeps
    only businesses worth pitching a website to."""

    model_config = ConfigDict(extra="forbid")

    min_rating: float | None = None
    max_rating: float | None = None
    min_reviews: int | None = None
    max_reviews: int | None = None
    web_presence: list[WebPresence] = Field(default_factory=lambda: ["none", "social_only"])


class ScrapeParams(BaseModel):
    """Mirrors the row in scrape_jobs.params. The CMS form maps 1:1 to
    these fields; the worker deserialises and runs."""

    model_config = ConfigDict(extra="forbid")

    category: str = "businesses"
    country: str = "NL"
    cities: list[str] = Field(default_factory=list)
    areas: list[str] = Field(default_factory=list)
    max_results_per_area: int = 120
    language: str = "en"
    lead_type: LeadType = "website"
    with_reviews: bool = True
    review_limit: int = 10
    filters: ScrapeFilters = Field(default_factory=ScrapeFilters)


class Lead(BaseModel):
    """Scraped row, ready to hand to any Sink. Mirrors columns on
    public.leads. Optional fields default to None so partial scrapes
    don't break upserts."""

    model_config = ConfigDict(extra="forbid")

    # provenance
    external_id: str
    scrape_job_id: str | None = None
    primary_source: str = "google_maps"
    source_url: str | None = None

    # classification
    lead_type: LeadType = "website"
    category: str | None = None

    # identity
    business_name: str
    name_normalized: str
    description: str | None = None
    about: str | None = None

    # location
    country: str | None = None
    region: str | None = None
    city: str | None = None
    address: str | None = None
    postal_code: str | None = None
    lat: float | None = None
    lng: float | None = None

    # contact / links
    phone: str | None = None
    email: str | None = None
    website_url: str | None = None
    facebook_url: str | None = None
    instagram_url: str | None = None
    menu_url: str | None = None

    # digital presence
    web_presence: WebPresence = "unknown"

    # reviews / hours
    rating: float | None = None
    review_count: int | None = None
    reviews: list[dict[str, Any]] | None = None
    opening_hours: dict[str, str] | None = None
    photo_urls: list[str] = Field(default_factory=list)

    # extensibility
    extra: dict[str, Any] = Field(default_factory=dict)
