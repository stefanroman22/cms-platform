from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse

from ..core.config import settings
from ..core.limiter import limiter
from ..services.supabase_client import get_supabase_admin

router = APIRouter(tags=["forms"])


def _build_email_html(
    project_name: str,
    form_key: str,
    fields: dict[str, str],
    submitted_at: str,
) -> str:
    rows = "".join(
        f"""
        <tr>
          <td style="padding:8px 12px;font-weight:600;color:#52525b;
                     border-bottom:1px solid #f4f4f5;white-space:nowrap;
                     vertical-align:top">{key}</td>
          <td style="padding:8px 12px;color:#18181b;
                     border-bottom:1px solid #f4f4f5;word-break:break-word">{value}</td>
        </tr>
        """
        for key, value in fields.items()
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f9f9f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0"
         style="background:#f9f9f9;padding:40px 0">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0"
             style="background:#fff;border-radius:12px;
                    border:1px solid #e4e4e7;overflow:hidden;
                    max-width:600px;width:100%">
        <!-- Header -->
        <tr>
          <td style="background:#18181b;padding:24px 32px">
            <p style="margin:0;color:#fff;font-size:14px;font-weight:600;
                      letter-spacing:0.05em;text-transform:uppercase">{project_name}</p>
            <p style="margin:4px 0 0;color:#a1a1aa;font-size:12px">
              New form submission — <span style="font-family:monospace">{form_key}</span>
            </p>
          </td>
        </tr>
        <!-- Fields table -->
        <tr>
          <td style="padding:24px 32px 8px">
            <table width="100%" cellpadding="0" cellspacing="0"
                   style="border:1px solid #f4f4f5;border-radius:8px;
                           border-collapse:collapse;overflow:hidden">
              {rows}
            </table>
          </td>
        </tr>
        <!-- Footer -->
        <tr>
          <td style="padding:16px 32px 32px">
            <p style="margin:0;font-size:12px;color:#a1a1aa">
              Submitted {submitted_at} · Delivered by Roman Technologies CMS
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


@router.post("/{project_slug}/{form_key}")
@limiter.limit("5/10minutes")
async def submit_form(
    project_slug: str,
    form_key: str,
    request: Request,
    body: dict,
) -> JSONResponse:
    # ── 1. Resolve project ────────────────────────────────────────────────────
    sb = get_supabase_admin()
    proj_result = (
        sb.table("projects")
        .select("id, name, allowed_origins")
        .eq("slug", project_slug)
        .eq("is_active", True)
        .maybe_single()
        .execute()
    )
    if not proj_result or not proj_result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    project = proj_result.data
    allowed_origins: list[str] = project.get("allowed_origins") or []

    # ── 2. Origin check ───────────────────────────────────────────────────────
    origin = request.headers.get("origin", "")
    if allowed_origins and origin not in allowed_origins:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Origin not allowed for this project",
        )

    # ── 3. Resolve the email_config service for this form_key ─────────────────
    svc_result = (
        sb.table("project_services")
        .select("id, service_type_slug")
        .eq("project_id", project["id"])
        .eq("service_key", form_key)
        .eq("service_type_slug", "email_config")
        .maybe_single()
        .execute()
    )
    if not svc_result or not svc_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No email_config service found with key '{form_key}'",
        )

    svc_id = svc_result.data["id"]

    # Destination email lives in content_entries (where the CMS UI writes it
    # via the generic save path). Prefer the published value; fall back to
    # draft so a client can wire up forms before the first publish.
    ce_result = (
        sb.table("content_entries")
        .select("published_content, draft_content")
        .eq("project_service_id", svc_id)
        .single()
        .execute()
    )
    pub = (ce_result.data or {}).get("published_content") or {}
    draft = (ce_result.data or {}).get("draft_content") or {}
    destination = pub.get("destination_email") or draft.get("destination_email")
    if not destination:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email destination not configured for this form",
        )

    # ── 4. Sanitise fields (strings only, skip internal keys) ─────────────────
    fields = {
        k: str(v)
        for k, v in body.items()
        if isinstance(k, str) and not k.startswith("_") and v is not None
    }

    if not fields:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Form body must contain at least one field",
        )

    # ── 5. Build reply-to from common field names ─────────────────────────────
    reply_to = fields.get("email") or fields.get("Email") or fields.get("email_address") or None

    # ── 6. Send via Resend ────────────────────────────────────────────────────
    if not settings.RESEND_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email service not configured (RESEND_API_KEY missing)",
        )

    import resend  # local import so missing key doesn't crash startup

    resend.api_key = settings.RESEND_API_KEY

    submitted_at = datetime.now(UTC).strftime("%d %b %Y at %H:%M UTC")
    html = _build_email_html(
        project_name=project["name"],
        form_key=form_key,
        fields=fields,
        submitted_at=submitted_at,
    )

    params: resend.Emails.SendParams = {
        "from": f"{settings.RESEND_FROM_NAME} <{settings.RESEND_FROM_EMAIL}>",
        "to": [destination],
        "subject": f"New message from {project['name']} — {form_key}",
        "html": html,
        **({"reply_to": reply_to} if reply_to else {}),
    }

    try:
        resend.Emails.send(params)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Email delivery failed: {exc}",
        ) from exc

    return JSONResponse(
        content={"success": True},
        headers={"Access-Control-Allow-Origin": origin or "*"},
    )
