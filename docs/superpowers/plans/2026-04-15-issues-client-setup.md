# Issues & Client Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-project issue reporting to the CMS, set up the Laurian Duma client account, and lock project settings to admins only.

**Architecture:** A new `project_issues` Supabase table stores issues scoped by `project_id`. A new FastAPI router handles CRUD with the same auth pattern as `workspace.py`. The frontend adds an `IssueForm` + `IssueList` below the service grid on the project workspace page. Client creation and project assignment happen directly via Supabase MCP tools.

**Tech Stack:** FastAPI, Supabase (PostgreSQL), Next.js 15 App Router, TypeScript, Tailwind CSS, Lucide icons.

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `backend/auth_service/routers/issues.py` | **Create** | GET + POST endpoints for project issues |
| `backend/auth_service/models/schemas.py` | **Modify** | Add `IssueOut`, `IssueCreateRequest` schemas |
| `backend/auth_service/main.py` | **Modify** | Register issues router |
| `frontend/src/components/dashboard/IssueForm.tsx` | **Create** | Issue submission form |
| `frontend/src/components/dashboard/IssueList.tsx` | **Create** | Issue list with priority badges |
| `frontend/src/app/dashboard/[projectSlug]/page.tsx` | **Modify** | Mount IssueForm + IssueList below ServiceGrid |

---

## Task 1: Verify Project Settings Are Admin-Only

The settings block in `page.tsx` is already gated by `isAdmin`. Confirm it works correctly.

**Files:**
- Verify: `frontend/src/app/dashboard/[projectSlug]/page.tsx`

- [ ] **Step 1: Confirm the guard**

Open `frontend/src/app/dashboard/[projectSlug]/page.tsx` and locate the settings section. It must read:

```tsx
{isAdmin && settings !== null && (
  <div className="mt-12">
    ...Project Settings...
  </div>
)}
```

`isAdmin` is derived from `user?.is_admin ?? false` where `user` comes from the `useUser()` context, which reads the `is_admin` column from the `users` Supabase table. Any non-admin account will see `is_admin = false` and the block will not render.

- [ ] **Step 2: Confirm the backend guard**

Open `backend/auth_service/routers/workspace.py`. The settings endpoints already call `_require_admin`:

```python
@router.get("/projects/{project_slug}/settings", ...)
async def get_project_settings(project_slug: str, request: Request):
    user = await _require_admin(request)   # ← raises 403 for non-admins
    ...

@router.patch("/projects/{project_slug}/settings", ...)
async def update_project_settings(...):
    user = await _require_admin(request)   # ← raises 403 for non-admins
    ...
```

No changes required. ✓

- [ ] **Step 3: Commit confirmation**

```bash
git add .
git commit -m "docs: confirm project settings are admin-only (no code change needed)"
```

---

## Task 2: Create Client Account and Link to Project

Create the client auth user in Supabase, insert into the `users` table, and set as the project owner.

**Tools used:** Supabase MCP (`mcp__supabase__execute_sql`)

- [ ] **Step 1: Create Supabase Auth user**

Use `mcp__supabase__execute_sql` on project `xeluydwpgiddbamysgyu` to check whether the user already exists:

```sql
SELECT id, email FROM auth.users WHERE email = 'd_laurian@yahoo.com';
```

If the row exists, skip to Step 3. If not, continue to Step 2.

- [ ] **Step 2: Create auth user via admin API**

Call `POST /admin/clients` via the CMS admin API (the endpoint built in the previous session):

```bash
curl -X POST http://localhost:8001/admin/clients \
  -H "Content-Type: application/json" \
  -H "Cookie: access_token=<your-admin-token>" \
  -d '{"email": "d_laurian@yahoo.com", "full_name": "Laurian Duma"}'
```

This creates the Supabase Auth user + `users` table row automatically. Note the returned `id`.

**Alternative (Supabase dashboard):** Go to Authentication → Users → Invite user → enter `d_laurian@yahoo.com`. Then set a temporary password and have the client change it.

**Set the password to `Viataefrumoasa!`** either via the dashboard (Authentication → Users → Reset password) or via SQL:

```sql
-- Only works if you have direct DB access; otherwise use Supabase Auth admin API
SELECT auth.uid(); -- confirm you're connected
```

Use the Supabase Dashboard → Authentication → Users → find `d_laurian@yahoo.com` → "Send password reset" or set manually.

- [ ] **Step 3: Get the client's user ID**

```sql
SELECT id FROM auth.users WHERE email = 'd_laurian@yahoo.com';
```

Note the UUID returned as `<CLIENT_UUID>`.

- [ ] **Step 4: Assign the client as project owner**

```sql
UPDATE projects
SET user_id = '<CLIENT_UUID>'
WHERE slug = 'laurian-duma-portfolio';

-- Verify
SELECT id, name, slug, user_id FROM projects WHERE slug = 'laurian-duma-portfolio';
```

Expected: the `user_id` column now holds `<CLIENT_UUID>`.

- [ ] **Step 5: Verify the users table row**

```sql
SELECT id, email, full_name, is_admin, is_active
FROM users
WHERE email = 'd_laurian@yahoo.com';
```

Expected: `is_admin = false`, `is_active = true`.

- [ ] **Step 6: Commit**

```bash
git add .
git commit -m "chore: client account d_laurian@yahoo.com created and linked to laurian-duma-portfolio"
```

---

## Task 3: Supabase Migration — project_issues Table

- [ ] **Step 1: Apply migration**

Run via `mcp__supabase__execute_sql` on project `xeluydwpgiddbamysgyu`:

```sql
CREATE TABLE IF NOT EXISTS project_issues (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    description TEXT NOT NULL,
    priority    TEXT NOT NULL DEFAULT 'Medium'
                    CHECK (priority IN ('High', 'Medium', 'Low')),
    created_by  UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS project_issues_project_id_idx
    ON project_issues (project_id);
CREATE INDEX IF NOT EXISTS project_issues_created_at_idx
    ON project_issues (project_id, created_at DESC);
```

- [ ] **Step 2: Verify table exists**

```sql
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'project_issues'
ORDER BY ordinal_position;
```

Expected columns: `id`, `project_id`, `title`, `description`, `priority`, `created_by`, `created_at`.

- [ ] **Step 3: Commit**

```bash
git add .
git commit -m "feat: add project_issues table migration"
```

---

## Task 4: Backend Schemas

**Files:**
- Modify: `backend/auth_service/models/schemas.py`

- [ ] **Step 1: Add issue schemas**

Append to the end of `backend/auth_service/models/schemas.py`:

```python
# ── Issues ───────────────────────────────────────────────────────────────────

class IssueCreateRequest(BaseModel):
    title: str
    description: str
    priority: str = "Medium"

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        if v not in ("High", "Medium", "Low"):
            raise ValueError("priority must be High, Medium, or Low")
        return v


class IssueOut(BaseModel):
    id: str
    project_id: str
    title: str
    description: str
    priority: str
    created_by: str | None
    created_by_email: str | None
    created_at: str
```

- [ ] **Step 2: Add the field_validator import**

At the top of `schemas.py`, update the pydantic import line from:

```python
from pydantic import BaseModel, EmailStr
```

to:

```python
from pydantic import BaseModel, EmailStr, field_validator
```

- [ ] **Step 3: Commit**

```bash
git add backend/auth_service/models/schemas.py
git commit -m "feat: add IssueCreateRequest and IssueOut schemas"
```

---

## Task 5: Backend Issues Router

**Files:**
- Create: `backend/auth_service/routers/issues.py`

- [ ] **Step 1: Create the router file**

Create `backend/auth_service/routers/issues.py` with this content:

```python
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, HTTPException, Request, status

from ..models.schemas import IssueCreateRequest, IssueOut
from ..services.auth_service import get_user_from_access_token
from ..services.supabase_client import get_supabase
from ..models.schemas import UserOut

router = APIRouter(tags=["issues"])

ACCESS_COOKIE = "access_token"


async def _require_user(request: Request) -> UserOut:
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user = await get_user_from_access_token(token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return user


def _require_project_access(project_slug: str, user: UserOut) -> dict:
    sb = get_supabase()
    result = (
        sb.table("projects")
        .select("id, name, slug, user_id, is_active")
        .eq("slug", project_slug)
        .eq("is_active", True)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    project = result.data
    if project["user_id"] != user.id and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return project


@router.get("/projects/{project_slug}/issues", response_model=List[IssueOut])
async def list_issues(project_slug: str, request: Request):
    user = await _require_user(request)
    project = _require_project_access(project_slug, user)

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
    user = await _require_user(request)
    project = _require_project_access(project_slug, user)

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
```

- [ ] **Step 2: Commit**

```bash
git add backend/auth_service/routers/issues.py
git commit -m "feat: add issues router with list and create endpoints"
```

---

## Task 6: Register Issues Router in FastAPI App

**Files:**
- Modify: `backend/auth_service/main.py`

- [ ] **Step 1: Import and register**

In `backend/auth_service/main.py`, update the router import line from:

```python
from .routers import auth, projects, content, workspace
```

to:

```python
from .routers import auth, projects, content, workspace
from .routers.issues import router as issues_router
```

Then after `app.include_router(workspace.router)`, add:

```python
app.include_router(issues_router)
```

- [ ] **Step 2: Restart the backend and verify**

```bash
# In backend/ directory with venv active:
uvicorn auth_service.main:app --reload --port 8001
```

Then test:

```bash
curl -X GET http://localhost:8001/projects/laurian-duma-portfolio/issues \
  -H "Cookie: access_token=<your-admin-token>"
```

Expected: `[]` (empty array — no issues yet).

- [ ] **Step 3: Commit**

```bash
git add backend/auth_service/main.py
git commit -m "feat: register issues router in FastAPI app"
```

---

## Task 7: Frontend — IssueForm Component

**Files:**
- Create: `frontend/src/components/dashboard/IssueForm.tsx`

- [ ] **Step 1: Create the component**

```tsx
"use client";

import { useState } from "react";
import { AlertCircle } from "lucide-react";
import {
    dashboardInputCn,
    dashboardFieldLabelCn,
    dashboardSectionCardCn,
    dashboardErrorBannerCn,
} from "@/lib/styles";

interface IssueFormProps {
    projectSlug: string;
    onCreated: () => void;
}

const PRIORITY_OPTIONS = ["High", "Medium", "Low"] as const;

const PRIORITY_COLORS: Record<string, string> = {
    High:   "text-red-600 bg-red-50 border-red-200 dark:text-red-400 dark:bg-red-950 dark:border-red-800",
    Medium: "text-amber-600 bg-amber-50 border-amber-200 dark:text-amber-400 dark:bg-amber-950 dark:border-amber-800",
    Low:    "text-green-600 bg-green-50 border-green-200 dark:text-green-400 dark:bg-green-950 dark:border-green-800",
};

export function IssueForm({ projectSlug, onCreated }: IssueFormProps) {
    const [title, setTitle] = useState("");
    const [description, setDescription] = useState("");
    const [priority, setPriority] = useState<"High" | "Medium" | "Low">("Medium");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    async function handleSubmit(e: React.FormEvent) {
        e.preventDefault();
        if (!title.trim() || !description.trim()) return;
        setLoading(true);
        setError("");
        try {
            const r = await fetch(`/api/projects/${projectSlug}/issues`, {
                method: "POST",
                credentials: "include",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ title: title.trim(), description: description.trim(), priority }),
            });
            if (!r.ok) {
                const body = await r.json().catch(() => ({}));
                throw new Error(body.detail ?? "Failed to submit issue.");
            }
            setTitle("");
            setDescription("");
            setPriority("Medium");
            onCreated();
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to submit issue.");
        } finally {
            setLoading(false);
        }
    }

    return (
        <div className={dashboardSectionCardCn}>
            <div className="px-5 py-4 border-b border-zinc-100 dark:border-zinc-800">
                <div className="flex items-center gap-2">
                    <AlertCircle className="h-4 w-4 text-zinc-500 dark:text-zinc-400" />
                    <p className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">Report an Issue</p>
                </div>
                <p className="mt-0.5 text-xs text-zinc-400 dark:text-zinc-500">
                    Found something that needs fixing? Let us know and we&apos;ll take care of it.
                </p>
            </div>

            <form onSubmit={handleSubmit} className="p-5 space-y-4">
                {error && <div className={dashboardErrorBannerCn}>{error}</div>}

                <div>
                    <label className={dashboardFieldLabelCn}>Issue title</label>
                    <input
                        type="text"
                        required
                        value={title}
                        onChange={(e) => setTitle(e.target.value)}
                        placeholder="e.g. Contact form is not sending emails"
                        className={dashboardInputCn}
                    />
                </div>

                <div>
                    <label className={dashboardFieldLabelCn}>Description</label>
                    <p className="text-xs text-zinc-400 dark:text-zinc-500 mb-1.5">
                        Be as specific as possible — include the page name, section, what you expected, and what actually happens.
                    </p>
                    <textarea
                        required
                        rows={5}
                        value={description}
                        onChange={(e) => setDescription(e.target.value)}
                        placeholder={"On the Contact page, the 'Send' button shows a spinner but no confirmation email arrives. Tested on Chrome on Windows 11.\n\nExpected: receive confirmation email within 1 minute.\nActual: nothing received after 10 minutes."}
                        className={`${dashboardInputCn} resize-y`}
                    />
                </div>

                <div>
                    <label className={dashboardFieldLabelCn}>Priority</label>
                    <div className="flex gap-2 flex-wrap">
                        {PRIORITY_OPTIONS.map((p) => (
                            <button
                                key={p}
                                type="button"
                                onClick={() => setPriority(p)}
                                className={`px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors ${
                                    priority === p
                                        ? PRIORITY_COLORS[p]
                                        : "border-zinc-200 text-zinc-500 hover:border-zinc-300 dark:border-zinc-700 dark:text-zinc-400"
                                }`}
                            >
                                {p}
                            </button>
                        ))}
                    </div>
                </div>

                <div className="flex justify-end pt-1">
                    <button
                        type="submit"
                        disabled={loading || !title.trim() || !description.trim()}
                        className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors dark:bg-zinc-700 dark:hover:bg-zinc-600"
                    >
                        {loading ? "Submitting…" : "Submit issue"}
                    </button>
                </div>
            </form>
        </div>
    );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/dashboard/IssueForm.tsx
git commit -m "feat: add IssueForm component"
```

---

## Task 8: Frontend — IssueList Component

**Files:**
- Create: `frontend/src/components/dashboard/IssueList.tsx`

- [ ] **Step 1: Create the component**

```tsx
"use client";

import { AlertCircle, Clock } from "lucide-react";
import { dashboardSectionCardCn } from "@/lib/styles";

export interface Issue {
    id: string;
    project_id: string;
    title: string;
    description: string;
    priority: "High" | "Medium" | "Low";
    created_by: string | null;
    created_by_email: string | null;
    created_at: string;
}

interface IssueListProps {
    issues: Issue[];
    loading: boolean;
}

const PRIORITY_BADGE: Record<string, string> = {
    High:   "bg-red-50 text-red-600 border border-red-200 dark:bg-red-950 dark:text-red-400 dark:border-red-800",
    Medium: "bg-amber-50 text-amber-600 border border-amber-200 dark:bg-amber-950 dark:text-amber-400 dark:border-amber-800",
    Low:    "bg-green-50 text-green-600 border border-green-200 dark:bg-green-950 dark:text-green-400 dark:border-green-800",
};

function formatDate(iso: string): string {
    return new Date(iso).toLocaleDateString("en-GB", {
        day: "numeric", month: "short", year: "numeric",
    });
}

export function IssueList({ issues, loading }: IssueListProps) {
    if (loading) {
        return (
            <div className="space-y-3">
                {[...Array(2)].map((_, i) => (
                    <div key={i} className="h-20 rounded-xl border border-zinc-200 bg-white animate-pulse dark:border-zinc-800 dark:bg-zinc-900" />
                ))}
            </div>
        );
    }

    if (issues.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 py-10 text-center">
                <AlertCircle className="h-7 w-7 text-zinc-300 dark:text-zinc-600 mb-2" />
                <p className="text-sm text-zinc-400 dark:text-zinc-500">No issues reported yet.</p>
            </div>
        );
    }

    return (
        <div className="space-y-3">
            {issues.map((issue) => (
                <div key={issue.id} className={`${dashboardSectionCardCn} p-4`}>
                    <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2 flex-wrap mb-1">
                                <span className={`inline-block px-2 py-0.5 rounded-md text-[11px] font-semibold ${PRIORITY_BADGE[issue.priority]}`}>
                                    {issue.priority}
                                </span>
                                <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100 truncate">
                                    {issue.title}
                                </p>
                            </div>
                            <p className="text-xs text-zinc-500 dark:text-zinc-400 whitespace-pre-wrap line-clamp-3">
                                {issue.description}
                            </p>
                        </div>
                    </div>
                    <div className="flex items-center gap-1.5 mt-3 text-[11px] text-zinc-400 dark:text-zinc-500">
                        <Clock className="h-3 w-3" />
                        <span>{formatDate(issue.created_at)}</span>
                        {issue.created_by_email && (
                            <>
                                <span>·</span>
                                <span>{issue.created_by_email}</span>
                            </>
                        )}
                    </div>
                </div>
            ))}
        </div>
    );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/dashboard/IssueList.tsx
git commit -m "feat: add IssueList component"
```

---

## Task 9: Wire Issues into the Project Workspace Page

**Files:**
- Modify: `frontend/src/app/dashboard/[projectSlug]/page.tsx`

- [ ] **Step 1: Add imports**

At the top of `page.tsx`, add the new imports alongside the existing ones:

```tsx
import { IssueForm } from "@/components/dashboard/IssueForm";
import { IssueList } from "@/components/dashboard/IssueList";
import type { Issue } from "@/components/dashboard/IssueList";
```

- [ ] **Step 2: Add the issues fetch function**

Add after `fetchProject`:

```tsx
function fetchIssues(projectSlug: string): Promise<Issue[]> {
    return fetch(`/api/projects/${projectSlug}/issues`, {
        credentials: "include",
        cache: "no-store",
    }).then(async (r) => {
        if (!r.ok) return [];
        return r.json();
    });
}
```

- [ ] **Step 3: Add issues query**

Inside the `ProjectWorkspacePage` component, after the existing `useQuery` calls, add:

```tsx
const issuesKey = `issues:${projectSlug}`;
const { data: issues, loading: issuesLoading, refresh: refreshIssues } = useQuery<Issue[]>(
    issuesKey,
    () => fetchIssues(projectSlug),
    { ttl: 30 * 1000 }
);
```

- [ ] **Step 4: Add issues section to JSX**

At the bottom of the returned JSX, after the Project Settings block and before the closing `</div>`, add:

```tsx
{/* ── Issues ──────────────────────────────────────────────────────── */}
<div className="mt-12">
    <h2 className="flex items-center gap-2 text-sm font-semibold text-zinc-700 dark:text-zinc-300 mb-4">
        <AlertCircle className="h-4 w-4" />
        Issues
    </h2>

    <div className="space-y-6">
        <IssueForm
            projectSlug={projectSlug}
            onCreated={() => {
                cache.invalidate(issuesKey);
                refreshIssues();
            }}
        />
        <IssueList issues={issues ?? []} loading={issuesLoading} />
    </div>
</div>
```

- [ ] **Step 5: Add AlertCircle to the lucide-react import**

Update the import line at the top of `page.tsx`:

```tsx
import { ArrowLeft, ChevronRight, Settings, AlertCircle } from "lucide-react";
```

- [ ] **Step 6: Verify the page renders without errors**

Start the frontend dev server:

```bash
cd frontend && npm run dev
```

Open `http://localhost:3000/dashboard/laurian-duma-portfolio` and confirm:
- Services grid loads with page tabs
- Issues section appears below settings
- `IssueForm` renders with title, description, priority selector
- `IssueList` shows "No issues reported yet."

- [ ] **Step 7: Test the full flow**

1. Submit an issue via the form
2. Confirm the issue appears in `IssueList` immediately after submission
3. Log in as `d_laurian@yahoo.com` — confirm they see the same issues list and can submit their own

- [ ] **Step 8: Commit**

```bash
git add frontend/src/app/dashboard/[projectSlug]/page.tsx
git commit -m "feat: add issues section to project workspace page"
```

---

## Self-Review

**Spec coverage:**
| Requirement | Task |
|------------|------|
| Project settings admin-only | Task 1 — verified, already gated |
| Create client d_laurian@yahoo.com | Task 2 |
| Client linked to Laurian Duma portfolio | Task 2 Step 4 |
| DB table for issues | Task 3 |
| Issues: title, description, priority | Tasks 4–5 |
| Issues below services | Task 9 Step 4 |
| Issues visible to client and admin | Tasks 5 + 9 — `_require_project_access` allows project owner + admins |
| Issues per-project not global | Task 3 — `project_id` FK; Task 5 — query scoped by `project_id` |
| Encourage explicit description | Task 7 — placeholder text in `IssueForm` + helper text |

**No placeholders found.** All steps contain complete code or exact SQL.

**Type consistency:** `Issue` interface defined in `IssueList.tsx` is imported in `page.tsx`. `IssueOut` pydantic model matches the fields returned in the router. ✓
