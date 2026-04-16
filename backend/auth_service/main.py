from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .core.config import settings
from .core.limiter import limiter
from .routers import auth, projects, content, workspace
from .routers.issues import router as issues_router
from .routers.forms import router as forms_router

# ── Main app ──────────────────────────────────────────────────────────────────

app = FastAPI(title="CMS Auth Service", version="1.0.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# In development allow any localhost / LAN origin so the dev server works
# regardless of whether it's accessed via localhost, 127.0.0.1, or a LAN IP.
# In production only the explicit FRONTEND_ORIGINS list is accepted.
_cors_kwargs: dict = (
    {
        "allow_origin_regex": (
            r"http://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3})(:\d+)?"
        )
    }
    if settings.ENVIRONMENT == "development"
    else {"allow_origins": settings.cors_origins}
)

app.add_middleware(
    CORSMiddleware,
    **_cors_kwargs,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(content.router)
app.include_router(workspace.router)
app.include_router(issues_router)


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
