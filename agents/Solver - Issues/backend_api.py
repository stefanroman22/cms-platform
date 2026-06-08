"""HTTP client for the backend admin endpoints.

Used by finalize.py to:
- mark issues done via PATCH /admin/issues/{id}/status (with 3× exp backoff
  on 5xx; 4xx fails immediately as it indicates a permission or schema bug
  rather than a transient outage)
- post solver agent events (rejection / no-diff / crash / backend-error) via
  POST /admin/issues/{id}/agent-event (best-effort; log on failure but never
  raise — agent events are a visibility feature, not a correctness one).
"""

from __future__ import annotations

import logging
import os
import time

import requests
from requests.exceptions import HTTPError

logger = logging.getLogger(__name__)

_TIMEOUT = 15
_RETRY_BACKOFFS = (1.0, 2.0, 4.0)


def _backend_url() -> str:
    return os.environ["CMS_BACKEND_URL"].rstrip("/")


def _token() -> str:
    return os.environ["CMS_API_TOKEN"]


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_token()}",
        "Content-Type": "application/json",
        "User-Agent": "solver-agent/1.0",
    }


def trigger_issue_resolved(issue_id: str) -> dict:
    """PATCH /admin/issues/{id}/status with status='done'.

    Retries up to 3 times with exponential backoff (1s/2s/4s) on 5xx errors.
    Does NOT retry on 4xx (likely permission/schema bug — fail fast).
    Raises HTTPError on final failure or 4xx.
    """
    url = f"{_backend_url()}/admin/issues/{issue_id}/status"
    last_error: Exception | None = None

    for attempt, backoff in enumerate(_RETRY_BACKOFFS, start=1):
        try:
            response = requests.patch(
                url,
                headers=_headers(),
                json={"status": "done"},
                timeout=_TIMEOUT,
            )
            response.raise_for_status()
            return response.json()
        except HTTPError as e:
            last_error = e
            status_code = e.response.status_code if e.response is not None else 0
            if 400 <= status_code < 500:
                # Client error — don't retry.
                raise
            logger.warning(
                "trigger_issue_resolved attempt %d/%d failed: %s; sleeping %.1fs",
                attempt,
                len(_RETRY_BACKOFFS),
                e,
                backoff,
            )
            if attempt < len(_RETRY_BACKOFFS):
                time.sleep(backoff)
        except (ConnectionError, requests.exceptions.Timeout) as e:
            last_error = e
            logger.warning(
                "trigger_issue_resolved attempt %d/%d network error: %s; sleeping %.1fs",
                attempt,
                len(_RETRY_BACKOFFS),
                e,
                backoff,
            )
            if attempt < len(_RETRY_BACKOFFS):
                time.sleep(backoff)

    assert last_error is not None  # at least one attempt must have failed
    raise last_error


def notify_agent_event(issue_id: str, *, kind: str, reason: str) -> None:
    """POST /admin/issues/{id}/agent-event for a solver-side event.

    Best-effort: logs but never raises. Slack/observability is not allowed
    to break the workflow — if this fails, the DB state is still correct
    (release_issue_failed already committed the retry-counter increment).
    """
    url = f"{_backend_url()}/admin/issues/{issue_id}/agent-event"
    try:
        response = requests.post(
            url,
            headers=_headers(),
            json={"kind": kind, "reason": reason[:500]},
            timeout=_TIMEOUT,
        )
        if response.status_code >= 400:
            logger.warning(
                "notify_agent_event returned %d: %s",
                response.status_code,
                response.text[:200],
            )
    except Exception:
        logger.exception("notify_agent_event POST failed (swallowed)")
