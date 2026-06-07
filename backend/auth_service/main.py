import re
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Load backend/.env into os.environ for modules that read env directly
# (e.g. slack_notify). Vercel/production already injects env vars into
# os.environ, so this is a no-op there.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from .core.config import settings  # noqa: E402
from .core.limiter import limiter  # noqa: E402
from .core.security_headers import SecurityHeadersMiddleware  # noqa: E402
from .routers import auth, content, projects, publish, workspace  # noqa: E402
from .routers.admin_conversions import router as admin_conversions_router  # noqa: E402
from .routers.admin_leads import router as admin_leads_router  # noqa: E402
from .routers.admin_scrape_jobs import router as admin_scrape_jobs_router  # noqa: E402
from .routers.booking import router as booking_router  # noqa: E402
from .routers.booking_admin import router as booking_admin_router  # noqa: E402
from .routers.forms import router as forms_router  # noqa: E402
from .routers.issues import router as issues_router  # noqa: E402
from .routers.slack_events import router as slack_events_router  # noqa: E402

# ── Main app ──────────────────────────────────────────────────────────────────

# Docs/OpenAPI surface only exposed in development. In preview/production
# they are an info-disclosure surface (route inventory, request schemas,
# rate-limit shape) and conflict with the strict CSP set in vercel.json.
_DOCS_ENABLED = settings.ENVIRONMENT == "development"
app = FastAPI(
    title="CMS Auth Service",
    version="1.0.0",
    docs_url="/docs" if _DOCS_ENABLED else None,
    redoc_url="/redoc" if _DOCS_ENABLED else None,
    openapi_url="/openapi.json" if _DOCS_ENABLED else None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# CORS policy.
#
# Development: allow any localhost / LAN / *.vercel.app origin so local dev
# works regardless of how it's accessed.
#
# Production: allow the explicit FRONTEND_ORIGINS list PLUS any *.vercel.app
# subdomain. The wildcard is intentional — client websites host their
# production + preview deployments on *.vercel.app and need to call the
# public /content/* endpoints. Authenticated endpoints require the auth
# cookie which is scoped to the CMS frontend domain only (SameSite=None
# still means the browser won't send the cookie across-origin unless the
# backend trusts the caller's origin, and the portfolio doesn't have the
# cookie to begin with).
def _prod_origin_regex() -> str:
    explicit = [re.escape(o) for o in settings.cors_origins]
    vercel = r"https://[a-zA-Z0-9.-]+\.vercel\.app"
    if explicit:
        return "(" + "|".join(explicit) + ")" + f"|{vercel}"
    return vercel


# CORS / PNA branch on ENVIRONMENT (Literal["development", "preview", "production"]):
#   development → permissive regex (localhost, LAN, *.vercel.app); PNA enabled
#   preview     → same regex (Vercel preview deployments behave like dev)
#   production  → strict allowlist + *.vercel.app for client websites; PNA off
IS_PROD = settings.ENVIRONMENT == "production"

_cors_kwargs: dict = (
    {"allow_origin_regex": _prod_origin_regex()}
    if IS_PROD
    else {
        "allow_origin_regex": (
            r"http://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3})(:\d+)?"
            r"|https://[a-zA-Z0-9.-]+\.vercel\.app"
        )
    }
)

app.add_middleware(
    CORSMiddleware,
    **_cors_kwargs,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Private Network Access (Chrome 123+) ──────────────────────────────────────
# Chrome blocks HTTPS public-origin pages (e.g. *.vercel.app) from fetching
# loopback resources (localhost) unless the server acknowledges the
# `Access-Control-Request-Private-Network: true` preflight with
# `Access-Control-Allow-Private-Network: true`. Starlette's CORSMiddleware
# doesn't emit this header, so we inject it via a thin ASGI wrapper that runs
# AROUND the CORS middleware. Dev-mode only — in production the CMS is served
# from a public HTTPS host and PNA doesn't apply.
class _PrivateNetworkAccessMiddleware:
    def __init__(self, asgi_app):
        self.app = asgi_app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        wants_pna = any(
            k == b"access-control-request-private-network" and v == b"true"
            for k, v in scope.get("headers", [])
        )
        if not wants_pna:
            await self.app(scope, receive, send)
            return

        async def send_with_pna_header(message):
            if message["type"] == "http.response.start":
                headers_list = list(message.get("headers", []))
                headers_list.append((b"access-control-allow-private-network", b"true"))
                message["headers"] = headers_list
            await send(message)

        await self.app(scope, receive, send_with_pna_header)


if not IS_PROD:
    app.add_middleware(_PrivateNetworkAccessMiddleware)

app.add_middleware(SecurityHeadersMiddleware)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(content.router)
app.include_router(workspace.router)
app.include_router(issues_router)
app.include_router(admin_leads_router)
app.include_router(admin_scrape_jobs_router)
app.include_router(admin_conversions_router)
app.include_router(publish.router)
app.include_router(slack_events_router)
app.include_router(booking_router)
app.include_router(booking_admin_router)


@app.get("/health")
def health():
    return {"status": "ok"}


# ── Forms sub-app (open CORS — no credentials; per-project origin validation
#    is enforced inside the route handler, not at the CORS middleware level) ──

forms_app = FastAPI(title="CMS Forms", docs_url=None, redoc_url=None)

forms_app.state.limiter = limiter
forms_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

forms_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
    max_age=600,
)

forms_app.include_router(forms_router)

app.mount("/forms", forms_app)
