from pydantic import BaseModel, EmailStr, Field, field_validator


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
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
    current_password: str
    new_password: str


class ChangeNameRequest(BaseModel):
    full_name: str


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
    name: str
    type: str
    description: str
    budget_range: str | None = None
    timeline: str | None = None


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
    service_type_slug: str
    service_key: str
    label: str | None = None
    display_order: int = 0
    page_name: str = "General"
    item_schema: list[RepeaterItemField] | None = None  # required when service_type_slug == "repeater"


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
    website_url: str | None = None
    allowed_origins: list[str] = []


# ── Admin client management ──────────────────────────────────────────────────

class CreateClientRequest(BaseModel):
    email: EmailStr
    full_name: str | None = None


class CreateClientOut(BaseModel):
    id: str
    email: str
    full_name: str | None
    created: bool           # True = new account, False = existing account
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
    created_by: str | None
    created_by_email: str | None
    created_at: str
