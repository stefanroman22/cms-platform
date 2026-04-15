from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, HTTPException, Request, status

from ..models.schemas import IssueCreateRequest, IssueOut
from ..services.supabase_client import get_supabase
from .deps import require_user, require_project_access

router = APIRouter(tags=["issues"])


@router.get("/projects/{project_slug}/issues", response_model=List[IssueOut])
async def list_issues(project_slug: str, request: Request):
    user = await require_user(request)
    project = require_project_access(project_slug, user)

    sb = get_supabase()
    result = (
        sb.table("project_issues")
        .select("id, project_id, title, description, priority, created_by, created_at, users(email)")
        .eq("project_id", project["id"])
        .order("created_at", desc=True)
        .execute()
    )

    out = []
    for row in (result.data or []):
        user_row = row.get("users") or {}
        out.append(IssueOut(
            id=row["id"],
            project_id=row["project_id"],
            title=row["title"],
            description=row["description"],
            priority=row["priority"],
            created_by=row.get("created_by"),
            created_by_email=user_row.get("email"),
            created_at=row["created_at"],
        ))
    return out


@router.post("/projects/{project_slug}/issues", response_model=IssueOut, status_code=status.HTTP_201_CREATED)
async def create_issue(project_slug: str, body: IssueCreateRequest, request: Request):
    user = await require_user(request)
    project = require_project_access(project_slug, user)

    sb = get_supabase()
    now = datetime.now(timezone.utc).isoformat()

    result = (
        sb.table("project_issues")
        .insert({
            "project_id": project["id"],
            "title": body.title.strip(),
            "description": body.description.strip(),
            "priority": body.priority,
            "created_by": user.id,
            "created_at": now,
        })
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=500, detail="Issue could not be created.")
    row = result.data[0]
    return IssueOut(
        id=row["id"],
        project_id=row["project_id"],
        title=row["title"],
        description=row["description"],
        priority=row["priority"],
        created_by=row.get("created_by"),
        created_by_email=user.email,
        created_at=row["created_at"],
    )
