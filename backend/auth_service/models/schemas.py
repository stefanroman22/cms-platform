import re

from pydantic import BaseModel, EmailStr, Field, field_validator

# ── Shared validators ────────────────────────────────────────────────────────

# Slug pattern used by every project / service slug field. Lowercase
# letters, digits, hyphens; 1-64 chars. Closes BE-005 path-traversal
# concern when slugs are interpolated into Supabase storage keys
# (e.g. `{project_slug}/{service_key}/file.png`).
_SLUG_PATTERN = r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$"
# Generic short-text pattern: any printable except control characters.
_NO_CTRL_PATTERN = r"^[^\x00-\x1f\x7f]*$"


def _http_url_validator(v: str | None) -> str | None:
    """Reused by every model that accepts a URL field. Rejects
    `javascript:`, `data:`, `file:`, etc.  (BE-005 / BE-006)."""
    if v is None:
        return None
    v = v.strip()
    if not v:
        return None
    if not (v.startswith("http://") or v.startswith("https://")):
        raise ValueError("URL must start with http:// or https://")
    return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)
    remember_me: bool = False


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str | None = None
    is_admin: bool = False


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)


class ChangeNameRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=100, pattern=_NO_CTRL_PATTERN)


# ── Projects / Account ──────────────────────────────────────────────────────


class ProjectOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    slug: str
    is_active: bool
    website_url: str | None = None
    created_at: str
    updated_at: str


class AccountOut(BaseModel):
    id: str
    email: str
    full_name: str | None = None
    is_admin: bool = False
    created_at: str
    projects_count: int


class ProjectRequestIn(BaseModel):
    name: str = Field(min_length=1, max_length=200, pattern=_NO_CTRL_PATTERN)
    # `type` is checked against `PROJECT_TYPES` set in the route handler.
    type: str = Field(min_length=1, max_length=40)
    description: str = Field(min_length=1, max_length=10_000)
    budget_range: str | None = Field(default=None, max_length=40)
    timeline: str | None = Field(default=None, max_length=40)


# ── Workspace / Services ─────────────────────────────────────────────────────


class ServiceOut(BaseModel):
    id: str
    service_key: str
    label: str | None
    service_type_slug: str
    service_type_name: str
    service_type_icon: str
    display_order: int
    page_name: str
    last_updated: str | None


class ServiceDetailOut(BaseModel):
    id: str
    service_key: str
    label: str | None
    service_type_slug: str
    service_type_name: str
    service_type_icon: str
    display_order: int
    page_name: str
    schema: dict
    content: dict
    last_updated: str | None


class ContentSaveRequest(BaseModel):
    content: dict


class RepeaterItemField(BaseModel):
    key: str
    label: str
    type: str  # "string" | "richtext" | "url" | "tags"


class ServiceCreateRequest(BaseModel):
    # service_type_slug is one of a fixed set; route still validates
    # against the DB. Length cap blocks DoS via huge strings.
    service_type_slug: str = Field(min_length=1, max_length=64, pattern=_SLUG_PATTERN)
    # Used as a Supabase storage path component — must be slug-safe.
    service_key: str = Field(min_length=1, max_length=64, pattern=_SLUG_PATTERN)
    label: str | None = Field(default=None, max_length=120, pattern=_NO_CTRL_PATTERN)
    display_order: int = Field(default=0, ge=0, le=10_000)
    page_name: str = Field(default="General", min_length=1, max_length=80, pattern=_NO_CTRL_PATTERN)
    item_schema: list[RepeaterItemField] | None = (
        None  # required when service_type_slug == "repeater"
    )


# ── Admin ────────────────────────────────────────────────────────────────────


class ServiceTypeOut(BaseModel):
    slug: str
    name: str
    description: str | None
    icon: str
    schema: dict


class AdminProjectOut(BaseModel):
    id: str
    name: str
    slug: str
    is_active: bool
    created_at: str
    user_id: str
    user_email: str | None
    user_full_name: str | None


class UserAdminOut(BaseModel):
    id: str
    email: str
    full_name: str | None
    is_admin: bool
    is_active: bool
    created_at: str
    projects_count: int


class ProjectSettingsOut(BaseModel):
    website_url: str | None
    allowed_origins: list[str]


class ProjectSettingsIn(BaseModel):
    website_url: str | None = Field(default=None, max_length=2000)
    allowed_origins: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("website_url", mode="after")
    @classmethod
    def _website_url_http(cls, v: str | None) -> str | None:
        return _http_url_validator(v)

    @field_validator("allowed_origins", mode="after")
    @classmethod
    def _origins_http(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for origin in v:
            checked = _http_url_validator(origin)
            if checked is None:
                raise ValueError("allowed_origins entries must be http(s) URLs")
            if len(checked) > 200:
                raise ValueError("allowed_origins entry too long")
            out.append(checked)
        return out


# ── Admin client management ──────────────────────────────────────────────────


class CreateClientRequest(BaseModel):
    email: EmailStr
    full_name: str | None = Field(default=None, max_length=100, pattern=_NO_CTRL_PATTERN)


class CreateClientOut(BaseModel):
    id: str
    email: str
    full_name: str | None
    created: bool  # True = new account, False = existing account
    generated_password: str | None = None  # only set when created=True


# ── Issues ───────────────────────────────────────────────────────────────────


class IssueCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10_000)
    priority: str = "Medium"

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        if v not in ("High", "Medium", "Low"):
            raise ValueError("priority must be High, Medium, or Low")
        return v


class IssueOut(BaseModel):
    id: str
    project_id: str
    title: str
    description: str
    priority: str
    status: str
    created_by: str | None
    created_by_email: str | None
    created_at: str


class IssueUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=10_000)
    priority: str | None = None

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str | None) -> str | None:
        if v is not None and v not in ("High", "Medium", "Low"):
            raise ValueError("priority must be High, Medium, or Low")
        return v


class IssueStatusRequest(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in ("pending", "in_progress", "done"):
            raise ValueError("status must be pending, in_progress, or done")
        return v


# ── Preview / Publish ────────────────────────────────────────────────────────


class PublishResponse(BaseModel):
    published_count: int
    last_published_at: str | None


class ProjectStatusOut(BaseModel):
    unpublished_count: int
    last_published_at: str | None
    preview_url: str | None
    production_url: str | None


class RotateTokenResponse(BaseModel):
    preview_token: str


class AdminProjectPatchIn(BaseModel):
    github_repo: str | None = Field(default=None, max_length=200)
    # Production branch (`main` for new repos per Option A guideline,
    # `master` tolerated for legacy repos). Persisted so the Solver
    # Agent's clone+reset path knows which ref to base cms-preview on.
    # Allowlist excludes shell metacharacters — defense in depth since
    # the value flows into subprocess git calls.
    production_branch: str | None = Field(default=None, min_length=1, max_length=80)
    vercel_project_id: str | None = Field(default=None, max_length=80)
    # URL fields stored as str (mocks + supabase serialisation need str
    # not pydantic Url objects) but validated as http(s) so admin / agent
    # can't inject `javascript:` or other non-web schemes that the
    # welcome email renders as a clickable CTA. Audit BE-004 / BE-006.
    production_url: str | None = Field(default=None, max_length=2000)
    preview_url: str | None = Field(default=None, max_length=2000)
    website_url: str | None = Field(default=None, max_length=2000)
    # `preview_token` deliberately omitted: rotation must go through
    # the dedicated POST /admin/projects/{slug}/rotate-preview-token
    # endpoint, which logs + cycles the token. Patching it here would
    # let an admin (or stolen Bearer key) fix the token to a value
    # they already know — token-fixation against /content/{slug}/draft.
    # Audit finding BE-004.

    @field_validator("production_url", "preview_url", "website_url", mode="after")
    @classmethod
    def _http_only(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    @field_validator("production_branch", mode="after")
    @classmethod
    def _safe_ref_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("production_branch cannot be empty")
        if not re.fullmatch(r"[A-Za-z0-9._/-]+", v):
            raise ValueError("production_branch contains invalid characters")
        return v


class AdminProjectDetailOut(BaseModel):
    slug: str
    name: str
    github_repo: str | None = None
    production_branch: str | None = None
    vercel_project_id: str | None = None
    production_url: str | None = None
    preview_url: str | None = None
    preview_token: str | None = None
    last_published_at: str | None = None


class AdminProjectCreateIn(BaseModel):
    # Used as URL component AND Supabase storage path component, so
    # slug-safe pattern is mandatory.
    slug: str = Field(min_length=1, max_length=64, pattern=_SLUG_PATTERN)
    name: str = Field(min_length=1, max_length=200, pattern=_NO_CTRL_PATTERN)
    owner_email: EmailStr
    github_repo: str | None = Field(default=None, max_length=200)


class ProjectTransferIn(BaseModel):
    to_user_email: EmailStr


class WelcomeEmailIn(BaseModel):
    project_slug: str = Field(min_length=1, max_length=64, pattern=_SLUG_PATTERN)
    project_name: str = Field(min_length=1, max_length=200, pattern=_NO_CTRL_PATTERN)
    website_url: str = Field(min_length=1, max_length=2000)

    @field_validator("website_url", mode="after")
    @classmethod
    def _website_url_http(cls, v: str) -> str:
        checked = _http_url_validator(v)
        if checked is None:
            raise ValueError("website_url must be a non-empty http(s) URL")
        return checked
