from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, status

from ..models.schemas import IssueCreateRequest, IssueOut, IssueStatusRequest, IssueUpdateRequest
from ..services import slack_notify
from ..services.supabase_client import get_supabase_admin
from .deps import require_project_access, require_user

router = APIRouter(tags=["issues"])


@router.get("/projects/{project_slug}/issues", response_model=list[IssueOut])
async def list_issues(project_slug: str, request: Request):
    user = await require_user(request)
    project = require_project_access(project_slug, user)

    sb = get_supabase_admin()
    result = (
        sb.table("project_issues")
        .select(
            "id, project_id, title, description, priority, status, created_by, created_at, users(email)"
        )
        .eq("project_id", project["id"])
        .order("created_at", desc=True)
        .execute()
    )

    out = []
    for row in result.data or []:
        user_row = row.get("users") or {}
        out.append(
            IssueOut(
                id=row["id"],
                project_id=row["project_id"],
                title=row["title"],
                description=row["description"],
                priority=row["priority"],
                status=row.get("status", "pending"),
                created_by=row.get("created_by"),
                created_by_email=user_row.get("email"),
                created_at=row["created_at"],
            )
        )
    return out


@router.post(
    "/projects/{project_slug}/issues", response_model=IssueOut, status_code=status.HTTP_201_CREATED
)
async def create_issue(project_slug: str, body: IssueCreateRequest, request: Request):
    user = await require_user(request)
    project = require_project_access(project_slug, user)

    sb = get_supabase_admin()
    now = datetime.now(UTC).isoformat()

    result = (
        sb.table("project_issues")
        .insert(
            {
                "project_id": project["id"],
                "title": body.title.strip(),
                "description": body.description.strip(),
                "priority": body.priority,
                "created_by": user.id,
                "created_at": now,
            }
        )
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=500, detail="Issue could not be created.")
    row = result.data[0]
    issue_out = IssueOut(
        id=row["id"],
        project_id=row["project_id"],
        title=row["title"],
        description=row["description"],
        priority=row["priority"],
        status="pending",
        created_by=row.get("created_by"),
        created_by_email=user.email,
        created_at=row["created_at"],
    )

    try:
        slack_notify.notify_issue_created(
            issue={
                "id": row["id"],
                "title": row["title"],
                "description": row["description"],
                "priority": row["priority"],
                "created_at": row["created_at"],
            },
            project=project,
            user_email=user.email,
        )
    except Exception:  # noqa: BLE001 — Slack must never break issue creation
        import logging

        logging.getLogger(__name__).exception("slack_notify (created) raised")

    return issue_out


@router.patch("/projects/{project_slug}/issues/{issue_id}", response_model=IssueOut)
async def update_issue(
    project_slug: str,
    issue_id: str,
    body: IssueUpdateRequest,
    request: Request,
):
    user = await require_user(request)
    project = require_project_access(project_slug, user)

    sb = get_supabase_admin()
    issue_result = (
        sb.table("project_issues")
        .select("id, project_id, created_by")
        .eq("id", issue_id)
        .eq("project_id", project["id"])
        .maybe_single()
        .execute()
    )
    if not issue_result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found.")

    row = issue_result.data
    if not user.is_admin and row.get("created_by") != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You can only edit your own issues."
        )

    update_data: dict = {}
    if body.title is not None:
        update_data["title"] = body.title.strip()
    if body.description is not None:
        update_data["description"] = body.description.strip()
    if body.priority is not None:
        update_data["priority"] = body.priority

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No fields to update."
        )

    updated = sb.table("project_issues").update(update_data).eq("id", issue_id).execute()
    if not updated.data:
        raise HTTPException(status_code=500, detail="Issue could not be updated.")

    r = updated.data[0]
    email_result = (
        (sb.table("users").select("email").eq("id", r["created_by"]).maybe_single().execute())
        if r.get("created_by")
        else None
    )

    return IssueOut(
        id=r["id"],
        project_id=r["project_id"],
        title=r["title"],
        description=r["description"],
        priority=r["priority"],
        status=r.get("status", "pending"),
        created_by=r.get("created_by"),
        created_by_email=(
            email_result.data.get("email") if email_result and email_result.data else None
        ),
        created_at=r["created_at"],
    )


@router.delete(
    "/projects/{project_slug}/issues/{issue_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_issue(project_slug: str, issue_id: str, request: Request):
    user = await require_user(request)
    project = require_project_access(project_slug, user)

    sb = get_supabase_admin()
    issue_result = (
        sb.table("project_issues")
        .select("id, created_by")
        .eq("id", issue_id)
        .eq("project_id", project["id"])
        .maybe_single()
        .execute()
    )
    if not issue_result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found.")

    row = issue_result.data
    if not user.is_admin and row.get("created_by") != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You can only delete your own issues."
        )

    sb.table("project_issues").delete().eq("id", issue_id).execute()


@router.patch(
    "/projects/{project_slug}/issues/{issue_id}/status",
    response_model=IssueOut,
)
async def update_issue_status(
    project_slug: str,
    issue_id: str,
    body: IssueStatusRequest,
    request: Request,
):
    user = await require_user(request)
    project = require_project_access(project_slug, user)

    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can update issue status.",
        )

    sb = get_supabase_admin()
    issue_result = (
        sb.table("project_issues")
        .select("id, project_id, status")
        .eq("id", issue_id)
        .eq("project_id", project["id"])
        .maybe_single()
        .execute()
    )
    if not issue_result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found.")

    old_status = issue_result.data.get("status", "pending")

    updated = (
        sb.table("project_issues").update({"status": body.status}).eq("id", issue_id).execute()
    )
    if not updated.data:
        raise HTTPException(status_code=500, detail="Status could not be updated.")

    r = updated.data[0]
    email_result = (
        (sb.table("users").select("email").eq("id", r["created_by"]).maybe_single().execute())
        if r.get("created_by")
        else None
    )

    issue_out = IssueOut(
        id=r["id"],
        project_id=r["project_id"],
        title=r["title"],
        description=r["description"],
        priority=r["priority"],
        status=r["status"],
        created_by=r.get("created_by"),
        created_by_email=(
            email_result.data.get("email") if email_result and email_result.data else None
        ),
        created_at=r["created_at"],
    )

    if old_status != "done" and body.status == "done":
        try:
            slack_notify.notify_issue_resolved(
                issue={"id": r["id"], "title": r["title"]},
                project=project,
                resolver_email=user.email,
            )
        except Exception:  # noqa: BLE001 — Slack must never break status update
            import logging

            logging.getLogger(__name__).exception("slack_notify (resolved) raised")

    return issue_out
