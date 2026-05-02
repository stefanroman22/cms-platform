# Issues Board, Cursor Polish & Email Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the per-project issue system with edit/delete/status management, a three-section kanban board (Open / In Progress / Done) with priority+date sorting, fix `cursor-pointer` on all CMS buttons, and install the Resend package so the email submission endpoint works end-to-end.

**Architecture:** The `project_issues` table gains a `status` column. The backend adds `PATCH` (edit), `DELETE`, and `PATCH .../status` endpoints with ownership guards — clients edit/delete only their own issues, admins can touch any. The frontend `IssueList.tsx` is fully rewritten as a self-contained board: client-side sort toggle (priority-first or date-first), three labelled sections, inline edit rows, and admin-only status transition buttons. Email uses the existing `forms.py` + Resend integration; only the package install in the shared venv is missing.

**Tech Stack:** FastAPI, Pydantic v2, supabase-py 2.10, Next.js 15 App Router, TypeScript, Tailwind CSS, Resend (email), Supabase PostgreSQL.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| Supabase DB | Migrate | Add `status TEXT NOT NULL DEFAULT 'pending'` to `project_issues` |
| `backend/auth_service/models/schemas.py` | Modify | Add `status` to `IssueOut`; add `IssueUpdateRequest`, `IssueStatusRequest` |
| `backend/auth_service/routers/issues.py` | Modify | Update GET (include `status`); add PATCH edit, DELETE, PATCH status endpoints |
| `frontend/src/components/dashboard/IssueList.tsx` | Full rewrite | Board with sections, sort, inline edit, delete, admin status controls |
| `frontend/src/app/dashboard/[projectSlug]/page.tsx` | Modify | Pass `isAdmin` + `currentUserId` to `IssueList` |
| `frontend/src/components/dashboard/IssueForm.tsx` | Modify | Add `cursor-pointer` to priority buttons |
| Various dashboard components | Modify | Add `cursor-pointer` to all `<button>` elements missing it |
| `backend/venv` | Install | `pip install resend==2.7.0` (already in requirements.txt, not in venv) |

---

## Task 1: Add `status` column to `project_issues`

**Files:**
- DB only (run SQL via Supabase MCP tool `mcp__supabase__execute_sql` against project `xeluydwpgiddbamysgyu`)

- [ ] **Step 1: Apply migration**

```sql
ALTER TABLE project_issues
ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'pending'
CONSTRAINT project_issues_status_check CHECK (status IN ('pending', 'in_progress', 'done'));
```

Run via `mcp__supabase__execute_sql` with `project_id: "xeluydwpgiddbamysgyu"`.

- [ ] **Step 2: Verify column exists**

```sql
SELECT column_name, data_type, column_default, is_nullable
FROM information_schema.columns
WHERE table_name = 'project_issues' AND column_name = 'status';
```

Expected: 1 row, `column_default = 'pending'::text`, `is_nullable = 'NO'`.

- [ ] **Step 3: Note — no commit needed (DB-only change). Proceed to Task 2.**

---

## Task 2: Update backend schemas

**Files:**
- Modify: `backend/auth_service/models/schemas.py`

Current `IssueOut` (lines ~179–188) and `IssueCreateRequest` (lines ~166–176) exist. You need to:
1. Add `status: str` field to `IssueOut`.
2. Add `IssueUpdateRequest` class.
3. Add `IssueStatusRequest` class.

- [ ] **Step 1: Read the current schemas file**

Read `backend/auth_service/models/schemas.py` lines 160–188 to find the exact current content of `IssueCreateRequest` and `IssueOut`.

- [ ] **Step 2: Add `status` to `IssueOut`**

Find the `IssueOut` class. It currently ends with `created_at: str`. Add `status: str` between `priority` and `created_by`:

```python
class IssueOut(BaseModel):
    id: str
    project_id: str
    title: str
    description: str
    priority: str
    status: str
    created_by: str | None
    created_by_email: str | None
    created_at: str
```

- [ ] **Step 3: Add `IssueUpdateRequest` and `IssueStatusRequest` after the existing classes**

Append these two classes immediately after `IssueOut`:

```python
class IssueUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=10_000)
    priority: str | None = None

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str | None) -> str | None:
        if v is not None and v not in ("High", "Medium", "Low"):
            raise ValueError("priority must be High, Medium, or Low")
        return v


class IssueStatusRequest(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in ("pending", "in_progress", "done"):
            raise ValueError("status must be pending, in_progress, or done")
        return v
```

`Field` and `field_validator` are already imported in this file (used by `IssueCreateRequest`). No new imports needed.

- [ ] **Step 4: Commit**

```bash
git add backend/auth_service/models/schemas.py
git commit -m "feat: add status to IssueOut, add IssueUpdateRequest and IssueStatusRequest schemas"
```

---

## Task 3: Add PATCH edit, DELETE, and PATCH status endpoints

**Files:**
- Modify: `backend/auth_service/routers/issues.py`

Read the current file first. Current imports line 6:
```python
from ..models.schemas import IssueCreateRequest, IssueOut
```

- [ ] **Step 1: Update the import line to include new schemas**

```python
from ..models.schemas import IssueCreateRequest, IssueOut, IssueUpdateRequest, IssueStatusRequest
```

- [ ] **Step 2: Update `list_issues` GET endpoint — include `status` in select and output**

Find the `.select(...)` call in `list_issues`. Change:
```python
.select("id, project_id, title, description, priority, created_by, created_at, users(email)")
```
to:
```python
.select("id, project_id, title, description, priority, status, created_by, created_at, users(email)")
```

In the `IssueOut(...)` constructor inside the loop, add `status=row.get("status", "pending")` after `priority=row["priority"]`.

- [ ] **Step 3: Update `create_issue` POST endpoint — include `status` in response**

In the `IssueOut(...)` return at the bottom of `create_issue`, add `status="pending"` after `priority=row["priority"]`.

- [ ] **Step 4: Add the `update_issue` PATCH endpoint**

Append after the existing `create_issue` function:

```python
@router.patch("/projects/{project_slug}/issues/{issue_id}", response_model=IssueOut)
async def update_issue(
    project_slug: str,
    issue_id: str,
    body: IssueUpdateRequest,
    request: Request,
):
    user = await require_user(request)
    project = require_project_access(project_slug, user)

    sb = get_supabase()
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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only edit your own issues.")

    update_data: dict = {}
    if body.title is not None:
        update_data["title"] = body.title.strip()
    if body.description is not None:
        update_data["description"] = body.description.strip()
    if body.priority is not None:
        update_data["priority"] = body.priority

    if not update_data:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No fields to update.")

    updated = (
        sb.table("project_issues")
        .update(update_data)
        .eq("id", issue_id)
        .execute()
    )
    if not updated.data:
        raise HTTPException(status_code=500, detail="Issue could not be updated.")

    r = updated.data[0]
    email_result = (
        sb.table("users")
        .select("email")
        .eq("id", r["created_by"])
        .maybe_single()
        .execute()
    ) if r.get("created_by") else None

    return IssueOut(
        id=r["id"],
        project_id=r["project_id"],
        title=r["title"],
        description=r["description"],
        priority=r["priority"],
        status=r.get("status", "pending"),
        created_by=r.get("created_by"),
        created_by_email=email_result.data.get("email") if email_result and email_result.data else None,
        created_at=r["created_at"],
    )
```

- [ ] **Step 5: Add the `delete_issue` DELETE endpoint**

```python
@router.delete(
    "/projects/{project_slug}/issues/{issue_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_issue(project_slug: str, issue_id: str, request: Request):
    user = await require_user(request)
    project = require_project_access(project_slug, user)

    sb = get_supabase()
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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only delete your own issues.")

    sb.table("project_issues").delete().eq("id", issue_id).execute()
```

- [ ] **Step 6: Add the `update_issue_status` PATCH endpoint (admin only)**

```python
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

    sb = get_supabase()
    issue_result = (
        sb.table("project_issues")
        .select("id, project_id")
        .eq("id", issue_id)
        .eq("project_id", project["id"])
        .maybe_single()
        .execute()
    )
    if not issue_result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found.")

    updated = (
        sb.table("project_issues")
        .update({"status": body.status})
        .eq("id", issue_id)
        .execute()
    )
    if not updated.data:
        raise HTTPException(status_code=500, detail="Status could not be updated.")

    r = updated.data[0]
    email_result = (
        sb.table("users")
        .select("email")
        .eq("id", r["created_by"])
        .maybe_single()
        .execute()
    ) if r.get("created_by") else None

    return IssueOut(
        id=r["id"],
        project_id=r["project_id"],
        title=r["title"],
        description=r["description"],
        priority=r["priority"],
        status=r["status"],
        created_by=r.get("created_by"),
        created_by_email=email_result.data.get("email") if email_result and email_result.data else None,
        created_at=r["created_at"],
    )
```

- [ ] **Step 7: Confirm the server starts cleanly**

```bash
cd backend
source venv/Scripts/activate
python -c "from auth_service.routers.issues import router; print('OK')"
```

Expected: `OK` (no import errors).

- [ ] **Step 8: Commit**

```bash
git add backend/auth_service/routers/issues.py
git commit -m "feat: add PATCH edit, DELETE, PATCH status endpoints to issues router"
```

---

## Task 4: Rewrite `IssueList.tsx` — full board with sections, sort, edit, delete, status

**Files:**
- Modify (full rewrite): `frontend/src/components/dashboard/IssueList.tsx`

This replaces the existing flat list with a board that has three sections (Open / In Progress / Done), client-side sort, inline edit rows, edit/delete buttons (own issues or admin), and admin-only status transition buttons.

- [ ] **Step 1: Replace the entire file content**

Write this as the new `frontend/src/components/dashboard/IssueList.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, Pencil, Trash2, X, Save } from "lucide-react";
import {
    dashboardSectionCardCn,
    dashboardInputCn,
    dashboardFieldLabelCn,
    dashboardErrorBannerCn,
} from "@/lib/styles";

type Priority = "High" | "Medium" | "Low";
type IssueStatus = "pending" | "in_progress" | "done";
type SortMode = "priority" | "date";

interface Issue {
    id: string;
    project_id: string;
    title: string;
    description: string;
    priority: Priority;
    status: IssueStatus;
    created_by: string | null;
    created_by_email: string | null;
    created_at: string;
}

export interface IssueListProps {
    projectSlug: string;
    refreshTrigger: number;
    isAdmin: boolean;
    currentUserId: string | null;
}

const PRIORITY_ORDER: Record<Priority, number> = { High: 0, Medium: 1, Low: 2 };

const priorityBadgeCn: Record<Priority, string> = {
    High:   "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-400",
    Medium: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-400",
    Low:    "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-400",
};

const prioritySelectedCn: Record<Priority, string> = {
    High:   "bg-red-100 dark:bg-red-950 text-red-700 dark:text-red-400",
    Medium: "bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-400",
    Low:    "bg-blue-100 dark:bg-blue-950 text-blue-700 dark:text-blue-400",
};

const priorityUnselectedCn =
    "bg-white dark:bg-zinc-900 text-zinc-500 dark:text-zinc-400 hover:bg-zinc-50 dark:hover:bg-zinc-800";

const SECTIONS: { status: IssueStatus; label: string; color: string }[] = [
    { status: "pending",     label: "Open",        color: "text-zinc-600 dark:text-zinc-400" },
    { status: "in_progress", label: "In Progress", color: "text-amber-600 dark:text-amber-400" },
    { status: "done",        label: "Done",        color: "text-emerald-600 dark:text-emerald-400" },
];

// Admin-only status transitions: what buttons to show per current status
const STATUS_TRANSITIONS: Record<IssueStatus, { label: string; next: IssueStatus }[]> = {
    pending:     [{ label: "Start",   next: "in_progress" }, { label: "Resolve", next: "done" }],
    in_progress: [{ label: "Resolve", next: "done" },        { label: "Reopen",  next: "pending" }],
    done:        [{ label: "Reopen",  next: "pending" }],
};

function sortIssues(issues: Issue[], mode: SortMode): Issue[] {
    return [...issues].sort((a, b) => {
        if (mode === "priority") {
            const pd = PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority];
            if (pd !== 0) return pd;
            const dd = new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
            if (dd !== 0) return dd;
            return a.title.localeCompare(b.title);
        } else {
            const dd = new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
            if (dd !== 0) return dd;
            const pd = PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority];
            if (pd !== 0) return pd;
            return a.title.localeCompare(b.title);
        }
    });
}

function formatDate(iso: string): string {
    return new Date(iso).toLocaleDateString([], {
        day: "numeric", month: "short", year: "numeric",
    });
}

export function IssueList({
    projectSlug,
    refreshTrigger,
    isAdmin,
    currentUserId,
}: IssueListProps) {
    const [issues, setIssues] = useState<Issue[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [sortMode, setSortMode] = useState<SortMode>("priority");

    // Inline edit state
    const [editingId, setEditingId] = useState<string | null>(null);
    const [editTitle, setEditTitle] = useState("");
    const [editDescription, setEditDescription] = useState("");
    const [editPriority, setEditPriority] = useState<Priority>("Medium");
    const [editSaving, setEditSaving] = useState(false);
    const [editError, setEditError] = useState<string | null>(null);

    // Action states
    const [deletingId, setDeletingId] = useState<string | null>(null);
    const [updatingStatusId, setUpdatingStatusId] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;

        async function fetchIssues() {
            setLoading(true);
            setError(null);
            try {
                const res = await fetch(`/api/projects/${projectSlug}/issues`, {
                    credentials: "include",
                    cache: "no-store",
                });
                if (!res.ok) throw new Error(`Failed to load issues (${res.status})`);
                const data: Issue[] = await res.json();
                if (!cancelled) setIssues(data);
            } catch (err) {
                if (!cancelled)
                    setError(err instanceof Error ? err.message : "Failed to load issues.");
            } finally {
                if (!cancelled) setLoading(false);
            }
        }

        fetchIssues();
        return () => {
            cancelled = true;
        };
    }, [projectSlug, refreshTrigger]);

    function startEdit(issue: Issue) {
        setEditingId(issue.id);
        setEditTitle(issue.title);
        setEditDescription(issue.description);
        setEditPriority(issue.priority);
        setEditError(null);
    }

    function cancelEdit() {
        setEditingId(null);
        setEditError(null);
    }

    async function saveEdit(issueId: string) {
        setEditSaving(true);
        setEditError(null);
        try {
            const res = await fetch(`/api/projects/${projectSlug}/issues/${issueId}`, {
                method: "PATCH",
                credentials: "include",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    title: editTitle.trim(),
                    description: editDescription.trim(),
                    priority: editPriority,
                }),
            });
            if (!res.ok) {
                const body = await res.json().catch(() => ({}));
                throw new Error(body.detail ?? `Save failed (${res.status})`);
            }
            const updated: Issue = await res.json();
            setIssues((prev) => prev.map((i) => (i.id === issueId ? updated : i)));
            setEditingId(null);
        } catch (err) {
            setEditError(err instanceof Error ? err.message : "Save failed.");
        } finally {
            setEditSaving(false);
        }
    }

    async function deleteIssue(issueId: string) {
        if (!confirm("Delete this issue? This cannot be undone.")) return;
        setDeletingId(issueId);
        try {
            await fetch(`/api/projects/${projectSlug}/issues/${issueId}`, {
                method: "DELETE",
                credentials: "include",
            });
            setIssues((prev) => prev.filter((i) => i.id !== issueId));
        } finally {
            setDeletingId(null);
        }
    }

    async function updateStatus(issueId: string, newStatus: IssueStatus) {
        setUpdatingStatusId(issueId);
        try {
            const res = await fetch(
                `/api/projects/${projectSlug}/issues/${issueId}/status`,
                {
                    method: "PATCH",
                    credentials: "include",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ status: newStatus }),
                }
            );
            if (!res.ok) return;
            const updated: Issue = await res.json();
            setIssues((prev) => prev.map((i) => (i.id === issueId ? updated : i)));
        } finally {
            setUpdatingStatusId(null);
        }
    }

    if (loading) {
        return (
            <div className="mt-4 space-y-2">
                {[0, 1, 2].map((i) => (
                    <div
                        key={i}
                        className="h-16 rounded-lg bg-zinc-100 dark:bg-zinc-800 animate-pulse"
                    />
                ))}
            </div>
        );
    }

    if (error) {
        return <div className={`mt-4 ${dashboardErrorBannerCn}`}>{error}</div>;
    }

    const sorted = sortIssues(issues, sortMode);

    return (
        <div className="mt-4">
            {/* Header: count + sort toggle */}
            <div className="flex items-center justify-between mb-3">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
                    {issues.length} {issues.length === 1 ? "Issue" : "Issues"}
                </h3>
                <div className="flex gap-1">
                    {(["priority", "date"] as SortMode[]).map((mode) => (
                        <button
                            key={mode}
                            type="button"
                            onClick={() => setSortMode(mode)}
                            className={[
                                "px-2.5 py-1 text-xs rounded-md font-medium transition-colors cursor-pointer",
                                sortMode === mode
                                    ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                                    : "bg-zinc-100 text-zinc-500 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-700",
                            ].join(" ")}
                        >
                            {mode === "priority" ? "By Priority" : "By Date"}
                        </button>
                    ))}
                </div>
            </div>

            {issues.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-10 text-center">
                    <CheckCircle2 className="h-8 w-8 text-zinc-300 dark:text-zinc-600 mb-2" />
                    <p className="text-sm text-zinc-400 dark:text-zinc-500">
                        No issues reported. All good!
                    </p>
                </div>
            ) : (
                <div className="space-y-6">
                    {SECTIONS.map(({ status, label, color }) => {
                        const sectionIssues = sorted.filter((i) => i.status === status);
                        return (
                            <div key={status}>
                                <p
                                    className={`text-xs font-semibold uppercase tracking-wider mb-2 ${color}`}
                                >
                                    {label} ({sectionIssues.length})
                                </p>
                                {sectionIssues.length === 0 ? (
                                    <p className="text-xs text-zinc-400 dark:text-zinc-500 pl-1">
                                        No issues here.
                                    </p>
                                ) : (
                                    <div
                                        className={`${dashboardSectionCardCn} divide-y divide-zinc-100 dark:divide-zinc-800`}
                                    >
                                        {sectionIssues.map((issue) => {
                                            const canEdit =
                                                isAdmin || issue.created_by === currentUserId;
                                            const isEditing = editingId === issue.id;
                                            const isDeleting = deletingId === issue.id;
                                            const isUpdatingStatus =
                                                updatingStatusId === issue.id;

                                            if (isEditing) {
                                                return (
                                                    <div
                                                        key={issue.id}
                                                        className="px-5 py-4 space-y-3"
                                                    >
                                                        {editError && (
                                                            <p className={dashboardErrorBannerCn}>
                                                                {editError}
                                                            </p>
                                                        )}
                                                        <div>
                                                            <label
                                                                className={dashboardFieldLabelCn}
                                                            >
                                                                Title
                                                            </label>
                                                            <input
                                                                type="text"
                                                                value={editTitle}
                                                                onChange={(e) =>
                                                                    setEditTitle(e.target.value)
                                                                }
                                                                className={dashboardInputCn}
                                                                autoFocus
                                                            />
                                                        </div>
                                                        <div>
                                                            <label
                                                                className={dashboardFieldLabelCn}
                                                            >
                                                                Description
                                                            </label>
                                                            <textarea
                                                                rows={4}
                                                                value={editDescription}
                                                                onChange={(e) =>
                                                                    setEditDescription(
                                                                        e.target.value
                                                                    )
                                                                }
                                                                className={`${dashboardInputCn} resize-none`}
                                                            />
                                                        </div>
                                                        <div>
                                                            <label
                                                                className={dashboardFieldLabelCn}
                                                            >
                                                                Priority
                                                            </label>
                                                            <div className="flex gap-0 rounded-lg border border-zinc-200 dark:border-zinc-700 overflow-hidden">
                                                                {(
                                                                    [
                                                                        "High",
                                                                        "Medium",
                                                                        "Low",
                                                                    ] as Priority[]
                                                                ).map((p) => (
                                                                    <button
                                                                        key={p}
                                                                        type="button"
                                                                        onClick={() =>
                                                                            setEditPriority(p)
                                                                        }
                                                                        className={`flex-1 py-1.5 text-sm font-medium transition-colors cursor-pointer ${
                                                                            editPriority === p
                                                                                ? prioritySelectedCn[p]
                                                                                : priorityUnselectedCn
                                                                        }`}
                                                                    >
                                                                        {p}
                                                                    </button>
                                                                ))}
                                                            </div>
                                                        </div>
                                                        <div className="flex gap-2 justify-end">
                                                            <button
                                                                type="button"
                                                                onClick={cancelEdit}
                                                                className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors cursor-pointer"
                                                            >
                                                                <X className="h-3.5 w-3.5" />
                                                                Cancel
                                                            </button>
                                                            <button
                                                                type="button"
                                                                onClick={() => saveEdit(issue.id)}
                                                                disabled={
                                                                    editSaving ||
                                                                    !editTitle.trim()
                                                                }
                                                                className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg bg-zinc-900 text-white hover:bg-zinc-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer"
                                                            >
                                                                <Save className="h-3.5 w-3.5" />
                                                                {editSaving ? "Saving…" : "Save"}
                                                            </button>
                                                        </div>
                                                    </div>
                                                );
                                            }

                                            return (
                                                <div
                                                    key={issue.id}
                                                    className="px-5 py-4 flex items-start gap-4"
                                                >
                                                    {/* Priority badge */}
                                                    <span
                                                        className={`mt-0.5 shrink-0 inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${priorityBadgeCn[issue.priority]}`}
                                                    >
                                                        {issue.priority}
                                                    </span>

                                                    {/* Content + admin status buttons */}
                                                    <div className="flex-1 min-w-0">
                                                        <p className="text-sm font-medium text-zinc-900 dark:text-zinc-50 truncate">
                                                            {issue.title}
                                                        </p>
                                                        <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400 line-clamp-2 whitespace-pre-wrap">
                                                            {issue.description}
                                                        </p>
                                                        {isAdmin && (
                                                            <div className="mt-2 flex gap-1.5 flex-wrap">
                                                                {STATUS_TRANSITIONS[
                                                                    issue.status
                                                                ].map(
                                                                    ({ label: btnLabel, next }) => (
                                                                        <button
                                                                            key={next}
                                                                            type="button"
                                                                            disabled={
                                                                                isUpdatingStatus
                                                                            }
                                                                            onClick={() =>
                                                                                updateStatus(
                                                                                    issue.id,
                                                                                    next
                                                                                )
                                                                            }
                                                                            className="px-2.5 py-0.5 text-xs rounded-full border border-zinc-200 dark:border-zinc-700 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-50 dark:hover:bg-zinc-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer"
                                                                        >
                                                                            {btnLabel}
                                                                        </button>
                                                                    )
                                                                )}
                                                            </div>
                                                        )}
                                                    </div>

                                                    {/* Meta + edit/delete actions */}
                                                    <div className="shrink-0 text-right space-y-1">
                                                        <p className="text-xs text-zinc-400 dark:text-zinc-500">
                                                            {issue.created_by_email ?? "Unknown"}
                                                        </p>
                                                        <p className="text-xs text-zinc-400 dark:text-zinc-500">
                                                            {formatDate(issue.created_at)}
                                                        </p>
                                                        {canEdit && (
                                                            <div className="flex gap-1 justify-end mt-1">
                                                                <button
                                                                    type="button"
                                                                    onClick={() => startEdit(issue)}
                                                                    className="flex items-center justify-center h-7 w-7 rounded-md text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors cursor-pointer"
                                                                    aria-label="Edit issue"
                                                                >
                                                                    <Pencil className="h-3.5 w-3.5" />
                                                                </button>
                                                                <button
                                                                    type="button"
                                                                    disabled={isDeleting}
                                                                    onClick={() =>
                                                                        deleteIssue(issue.id)
                                                                    }
                                                                    className="flex items-center justify-center h-7 w-7 rounded-md text-zinc-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950 disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer"
                                                                    aria-label="Delete issue"
                                                                >
                                                                    <Trash2 className="h-3.5 w-3.5" />
                                                                </button>
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/dashboard/IssueList.tsx
git commit -m "feat: rewrite IssueList as kanban board with sections, sort, edit, delete, status"
```

---

## Task 5: Wire `isAdmin` and `currentUserId` into workspace page

**Files:**
- Modify: `frontend/src/app/dashboard/[projectSlug]/page.tsx`

- [ ] **Step 1: Read the current page file**

Read `frontend/src/app/dashboard/[projectSlug]/page.tsx`. Find the `<IssueList>` usage (around line 184–188 based on current state) — it currently passes only `projectSlug` and `refreshTrigger`.

- [ ] **Step 2: Update the IssueList JSX to pass `isAdmin` and `currentUserId`**

Find:
```tsx
<IssueList
    projectSlug={projectSlug}
    refreshTrigger={issueRefreshKey}
/>
```

Replace with:
```tsx
<IssueList
    projectSlug={projectSlug}
    refreshTrigger={issueRefreshKey}
    isAdmin={isAdmin}
    currentUserId={user?.id ?? null}
/>
```

`isAdmin` is already derived from `useUser()` on line ~47. `user` is already destructured. No new imports or state needed.

- [ ] **Step 3: Commit**

```bash
git add "frontend/src/app/dashboard/[projectSlug]/page.tsx"
git commit -m "feat: pass isAdmin and currentUserId to IssueList"
```

---

## Task 6: Global `cursor-pointer` sweep — all CMS buttons

**Files:**
Read each file below, then add `cursor-pointer` to every `<button>` element that is missing it. Do NOT modify buttons that already have `cursor-pointer` or use `dashboardPrimaryBtnCn` (which already includes it).

- [ ] **Step 1: Audit `IssueForm.tsx` — priority buttons**

Read `frontend/src/components/dashboard/IssueForm.tsx`.

Find the priority `<button>` elements (in the segmented control, className uses `prioritySelectedCn`/`priorityUnselectedCn`). Their current class is:
```
`flex-1 py-1.5 text-sm font-medium transition-colors ${...}`
```

Add `cursor-pointer` to the className string:
```
`flex-1 py-1.5 text-sm font-medium transition-colors cursor-pointer ${...}`
```

- [ ] **Step 2: Audit `PageTabs.tsx`**

Read `frontend/src/components/dashboard/PageTabs.tsx`.

Find each `<button>` and add `cursor-pointer` to its className if missing.

- [ ] **Step 3: Audit `ServiceCard.tsx`**

Read `frontend/src/components/dashboard/ServiceCard.tsx`.

Find each `<button>` (including "Configure", "Remove" buttons) and add `cursor-pointer` if missing.

- [ ] **Step 4: Audit `editors/KeyValueEditor.tsx`**

Read `frontend/src/components/dashboard/editors/KeyValueEditor.tsx`.

Find the "Add row" button and the remove row button — add `cursor-pointer` if missing.

- [ ] **Step 5: Audit `editors/RepeaterEditor.tsx`**

Read `frontend/src/components/dashboard/editors/RepeaterEditor.tsx`.

Find all `<button>` elements — add `cursor-pointer` if missing.

- [ ] **Step 6: Audit `editors/ImageEditor.tsx`**

Read `frontend/src/components/dashboard/editors/ImageEditor.tsx`.

Find the "Choose file" button and the remove (X) button — add `cursor-pointer` if missing. Note: the "Choose file" button already has `disabled:cursor-not-allowed` but may be missing the base `cursor-pointer`.

- [ ] **Step 7: Audit `editors/GalleryEditor.tsx` and `editors/FloorPlanEditor.tsx`**

Read both files. Add `cursor-pointer` to any `<button>` elements missing it.

- [ ] **Step 8: Audit the project workspace page and the main dashboard page**

Run:
```bash
grep -rn "<button" frontend/src/app/dashboard/ --include="*.tsx"
```

For each `<button>` found, check if its `className` contains `cursor-pointer`. Add it if missing.

- [ ] **Step 9: Audit remaining dashboard components**

Run:
```bash
grep -rn "<button" frontend/src/components/dashboard/ --include="*.tsx" | grep -v "cursor-pointer"
```

For any hits, open the file and add `cursor-pointer` to the button's className.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/components/ frontend/src/app/dashboard/
git commit -m "fix: add cursor-pointer to all CMS button elements"
```

---

## Task 7: Install `resend` in the backend venv and verify email works

**Files:**
- Runtime only (venv install, no file changes needed — `resend==2.7.0` is already in `backend/auth_service/requirements.txt`)

- [ ] **Step 1: Install the package**

```bash
cd backend
source venv/Scripts/activate
pip install resend==2.7.0
```

Expected output includes: `Successfully installed resend-2.7.0` (or "Requirement already satisfied" if already installed).

- [ ] **Step 2: Verify import works**

```bash
python -c "import resend; print('resend OK:', resend.__version__)"
```

Expected: `resend OK: 2.7.0`

- [ ] **Step 3: Verify the forms endpoint loads**

```bash
python -c "from auth_service.routers.forms import router; print('forms router OK')"
```

Expected: `forms router OK`

- [ ] **Step 4: Confirm RESEND_API_KEY is set in `backend/auth_service/.env`**

Run:
```bash
grep RESEND_API_KEY backend/auth_service/.env
```

Expected: a line like `RESEND_API_KEY=re_...` (non-empty value). If the value is empty, the email endpoint will return 503 — the key must be set.

- [ ] **Step 5: Start the auth service and test the form endpoint with curl**

Start the server in background:
```bash
cd backend && source venv/Scripts/activate && python -m uvicorn auth_service.main:app --port 8001 &
sleep 3
```

Then submit a test form (replace `laurian-duma-portofolio-website` and `contact` with the actual project slug and email_config service key visible in the CMS dashboard):
```bash
curl -s -X POST http://localhost:8001/forms/laurian-duma-portofolio-website/contact \
  -H "Content-Type: application/json" \
  -H "Origin: http://localhost:3000" \
  -d '{"name": "Test User", "email": "test@example.com", "message": "This is a test form submission."}' \
  -w "\nHTTP_STATUS:%{http_code}"
```

Expected: `{"success":true}` with HTTP 200.

If you get 503 with "RESEND_API_KEY missing": set the key in `backend/auth_service/.env` — it should already be there.

If you get 404 "Project not found" or "No email_config service found": the project slug or service key is wrong — check the CMS dashboard to get the correct values.

- [ ] **Step 6: No commit needed — this task is runtime setup only.**

---

## Self-Review

**Spec coverage check:**
- ✅ Client edit own issues → Task 3 (PATCH endpoint with ownership check) + Task 4 (edit button shown for `canEdit = isAdmin || created_by === currentUserId`)
- ✅ Client delete own issues → Task 3 (DELETE endpoint) + Task 4 (delete button)
- ✅ Sort by priority (default) → Task 4 (`sortMode = "priority"` as initial state, `PRIORITY_ORDER` sort)
- ✅ Sort by date → Task 4 (date sort mode toggle button)
- ✅ Default sort: priority first, equal priority → latest first, equal time → alphabetical → Task 4 (`sortIssues` function)
- ✅ Admin: same sort options → Task 4 (sort is user-agnostic)
- ✅ Admin: mark as done / in progress → Task 3 (PATCH status endpoint) + Task 4 (`STATUS_TRANSITIONS` buttons shown when `isAdmin`)
- ✅ Three sections (Open / In Progress / Done) → Task 4 (`SECTIONS` array, filtered per status)
- ✅ Client sees real-time status → Task 4 (optimistic update via `setIssues` after status PATCH)
- ✅ Every button has `cursor-pointer` → Task 6
- ✅ Email fully functional → Task 7 (install resend, test endpoint)

**Placeholder scan:** None found.

**Type consistency:** `IssueStatus` type (`"pending" | "in_progress" | "done"`) used consistently across Tasks 3 and 4. `IssueOut.status: str` in the schema (Task 2) matches what the frontend's `Issue.status: IssueStatus` expects at runtime. `IssueUpdateRequest` and `IssueStatusRequest` defined in Task 2 and imported in Task 3.
