"""HTTP client for the backend admin endpoints.

Used by finalize.py to mark issues done via the new
PATCH /admin/issues/{id}/status route (which fires S1 Slack post +
persists slack_resolved_ts).
"""

from __future__ import annotations

import os

import requests


def _backend_url() -> str:
    return os.environ["CMS_BACKEND_URL"].rstrip("/")


def _token() -> str:
    return os.environ["CMS_API_TOKEN"]


def trigger_issue_resolved(issue_id: str, *, timeout: int = 15) -> dict:
    """PATCH /admin/issues/{id}/status with status='done'. Raises on non-2xx."""
    url = f"{_backend_url()}/admin/issues/{issue_id}/status"
    response = requests.patch(
        url,
        headers={
            "Authorization": f"Bearer {_token()}",
            "Content-Type": "application/json",
            "User-Agent": "solver-agent/1.0",
        },
        json={"status": "done"},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()
