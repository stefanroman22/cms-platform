"""Vercel Python entry point. Re-exports the FastAPI ASGI app so the
@vercel/python runtime can serve it as a serverless function.
"""
from auth_service.main import app  # noqa: F401 — re-export for Vercel
