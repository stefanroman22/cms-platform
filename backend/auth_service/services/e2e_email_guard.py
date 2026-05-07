"""TEST-002 — Skip the Resend hop on E2E test bodies in preview.

Every push to `dev` or `master` triggers the E2E suite, which on the
old code path fired a real Resend email through every send route
(forms, welcome, project request). That's noisy, costs delivery quota,
and risks hitting Resend's domain reputation.

The integration suite now stamps `[E2E-TEST]` into one of the user-
controlled fields of each request. When the backend sees that marker
in a preview deployment, it short-circuits the Resend call and returns
a mock id. Production never short-circuits — a real customer typing
``[E2E-TEST]`` into a form still has their submission delivered.

Why "preview" tier specifically: the dev/master push pipeline targets
preview, so this guard is on for the test environment and off in
production. Local development tests don't hit this code path because
they mock the resend module directly in unit tests.
"""

import logging

from ..core.config import settings

log = logging.getLogger(__name__)

E2E_MARKER = "[E2E-TEST]"


def should_short_circuit(*texts: str) -> bool:
    """True if this email is part of an E2E run AND we are in preview.

    Pass any user-controlled strings that together form the
    request body — the marker may live in the form payload, the project
    name, or the destination email. The check is preview-tier-gated so
    production cannot accidentally drop a real email.
    """
    if settings.ENVIRONMENT != "preview":
        return False
    for text in texts:
        if text and E2E_MARKER in text:
            return True
    return False


def short_circuit_response(reason: str) -> dict[str, str]:
    """Mock Resend response shape; logs the skip for observability."""
    log.info("e2e_email_guard: short-circuited Resend send (%s)", reason)
    return {"id": "e2e-test-skipped"}
