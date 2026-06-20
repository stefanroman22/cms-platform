# backend/auth_service/models/seo_schemas.py
"""Pydantic models for the SEO/GEO router. Plain BaseModel (house style)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SeoOverviewOut(BaseModel):
    enabled: bool
    blog_route: str | None = None
    last_run_at: str | None = None
    seo_score: int | None = None
    geo_score: int | None = None
    local_score: int | None = None
    last_status: str | None = None
    locales: list[str] = Field(default_factory=list)


class SeoPlanItemOut(BaseModel):
    id: str
    track: str
    title: str
    description: str
    rationale: str
    priority: int
    effort: str
    action_kind: str
    target: str | None = None
    status: str


class SeoRunOut(BaseModel):
    id: str
    status: str
    trigger: str
    summary: str | None = None
    scores: dict = Field(default_factory=dict)
    started_at: str
    finished_at: str | None = None


class SeoChangeOut(BaseModel):
    id: str
    kind: str
    target: str | None = None
    before: dict = Field(default_factory=dict)
    after: dict = Field(default_factory=dict)
    verified: dict = Field(default_factory=dict)
    reverted: bool
    applied_at: str
    published_at: str | None = None


class SeoHistoryOut(BaseModel):
    runs: list[SeoRunOut] = Field(default_factory=list)
    changes: list[SeoChangeOut] = Field(default_factory=list)


class SeoCompetitorOut(BaseModel):
    id: str
    name: str
    url: str | None = None
    location: str | None = None
    signals: dict = Field(default_factory=dict)
    analysis: str
    captured_at: str


class SeoPageMetaIn(BaseModel):
    route: str = Field(min_length=1, max_length=2000)
    locale: str = Field(min_length=2, max_length=10)
    title: str = Field(default="", max_length=300)
    description: str = Field(default="", max_length=600)
    canonical: str | None = Field(default=None, max_length=2000)
    og: dict = Field(default_factory=dict)
    json_ld: dict = Field(default_factory=dict)
    robots: str | None = Field(default=None, max_length=200)
    status: str = "draft"


class SeoPageMetaOut(SeoPageMetaIn):
    id: str
    updated_by: str
    updated_at: str


class SeoArticleIn(BaseModel):
    slug: str = Field(min_length=1, max_length=300)
    locale: str = Field(min_length=2, max_length=10)
    title: str = Field(default="", max_length=300)
    excerpt: str = Field(default="", max_length=1000)
    body: str = ""
    json_ld: dict = Field(default_factory=dict)
    hero_image_url: str | None = Field(default=None, max_length=2000)
    status: str = "draft"


class SeoArticleOut(SeoArticleIn):
    id: str
    updated_by: str
    created_at: str
    updated_at: str


class SeoTranslateIn(BaseModel):
    kind: str = "meta"  # 'meta' | 'article'


class SeoJobIn(BaseModel):
    kind: str = "run_full"


class SeoJobOut(BaseModel):
    id: str
    kind: str
    status: str
    requested_at: str
