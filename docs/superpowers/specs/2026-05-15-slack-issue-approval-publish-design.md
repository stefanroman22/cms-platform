# S1.5 — Slack Approval, Production Publish, Client Email

**Status:** Design approved 2026-05-15
**Owner:** Stefan Roman
**Scope:** Sub-project 1.5 of a 4-part roadmap toward an autonomous issue-resolution agent. Builds on S1 (outbound Slack notifications).

## Roadmap context

| Sub-project | Purpose | Status |
|---|---|---|
| **S1** | Outbound Slack notifications on issue create + resolve | shipped 2026-05-15 |
| **S1.5** | Inbound Slack listener: ✅ → publish + email client; text reply → revert + store feedback | this spec |
| **S2** | Verifier sub-agent — confirms reported issue actually exists in code | future |
| **S3** | Solver sub-agent — edits code, pushes to `cms-preview`, reads `revision_feedback` from this spec | future |

This spec **builds the rails** that S3 plugs into. The text-reply branch persists Stefan's feedback so S3 can later read it and auto-retry.

## Problem

Today, when Stefan resolves an issue:
- An "Issue Resolved" Slack post lands in `#issues-websites` (S1).
- The dev branch (`cms-preview`) has the fix.
- Nothing promotes it to production. Stefan must merge by hand.
- Client is never notified.

If Stefan wants to reject the fix (preview doesn't look right), there's no formal way to record that — he just keeps editing.

## Solution

Backend exposes `/slack/events`. Slack delivers `reaction_added` + `message.channels` events. Two flows:

- **✅ reaction on a tracked resolved-issue message** → backend fast-forwards `master` ref to `cms-preview` HEAD via GitHub API → Vercel auto-deploys production → Resend POSTs a branded email to the issue creator → bot posts "🚀 Promoted to production" in the Slack thread.
- **Text reply in the same thread (5+ chars, from Stefan only)** → backend sets issue `status = in_progress`, stores the text in `revision_feedback`, posts "📝 Marked as needs revision" in the thread. Stefan re-fixes manually; on the next resolved-message + ✅ react, the approval loop closes.

## Architecture

```
                    ┌──────────────────────────┐
                    │  Slack workspace          │
                    │  #issues-websites         │
                    └────────────┬──────────────┘
                                 │ event payloads
                                 │ (reaction_added, message.channels)
                                 ▼
        ┌──────────────────────────────────────────────────┐
        │ POST /slack/events  (new router)                │
        │  1. URL verification challenge response          │
        │  2. HMAC SHA-256 sig verify (SLACK_SIGNING_SECRET│
        │  3. Idempotency lookup (slack_processed_events)  │
        │  4. Dispatch by event["type"]                    │
        └─────────┬────────────────────┬───────────────────┘
                  │                    │
   reaction_added │                    │ message (thread reply)
                  ▼                    ▼
   ┌──────────────────────┐    ┌─────────────────────────┐
   │ handle_reaction      │    │ handle_message          │
   │   filter ✅ on bot's │    │   filter thread_ts on   │
   │   resolved-issue msg │    │   bot's resolved-issue  │
   │                      │    │   msg, skip bot replies │
   └──────┬───────────────┘    └──────┬──────────────────┘
          │                            │
          ▼                            ▼
   ┌──────────────────┐         ┌──────────────────────┐
   │ approve_issue()  │         │ revise_issue()       │
   │ - lookup issue   │         │ - status done →      │
   │ - github merge   │         │   in_progress        │
   │ - Resend email   │         │ - store feedback     │
   │ - Slack ack      │         │ - Slack ack reply    │
   └──────────────────┘         └──────────────────────┘
```

Returns 200 to Slack always (except 401 on bad signature). Slack retries on non-2xx; we never want that — idempotency table catches duplicate deliveries.

Work is inlined into the request (response is 1-4s). For S1.5 volume (~handful of approvals per day) this is fine, and avoids Vercel serverless lifetime hazards that `BackgroundTasks` introduces.

## Data model

### `project_issues`

```sql
ALTER TABLE project_issues
  ADD COLUMN slack_resolved_ts TEXT NULL,
  ADD COLUMN revision_feedback TEXT NULL,
  ADD COLUMN revision_feedback_at TIMESTAMPTZ NULL;
```

- `slack_resolved_ts` — Slack message timestamp (`"1715789123.001234"`) of the most recent "Issue Resolved" post. Lookup key for both reaction + thread-reply events.
- `revision_feedback` — Stefan's last rejection text (full body). Cleared when ✅ approves.
- `revision_feedback_at` — when it was submitted. Lets S3 know which feedback to use if multiple revisions.

### `projects`

```sql
ALTER TABLE projects
  ADD COLUMN production_branch TEXT NOT NULL DEFAULT 'master';
```

Backend needs to know which branch is the production ref for fast-forward. Default `'master'` matches observed repo state.

### Data fix (stale `repo_branch`)

S1 migration defaulted `repo_branch` to `'dev'`, but real client repos use `cms-preview`:

```sql
UPDATE projects
  SET repo_branch = 'cms-preview'
  WHERE repo_branch = 'dev'
    AND github_repo IS NOT NULL;
```

Run as part of S1.5 migration. The Slack messages from S1 currently misreport the branch — this also fixes that.

### `slack_processed_events` (idempotency)

```sql
CREATE TABLE IF NOT EXISTS slack_processed_events (
  event_id TEXT PRIMARY KEY,
  received_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_slack_processed_events_received_at
  ON slack_processed_events (received_at);
```

Slack sends `event_id` per event. Insert with `ON CONFLICT DO NOTHING` — duplicate deliveries short-circuit. Manual cleanup of rows older than 1 hour is acceptable at current volume; pg_cron sweep is a follow-up.

Migration filename: `backend/migrations/2026_05_15_slack_inbound_s1_5.sql`.

## Slack app changes

**New scopes** (require bot re-install):
- `reactions:read`
- `channels:history`

**Re-install** issues a new `xoxb-...` token. Old one is revoked. Update env var.

**Event subscriptions**:
- Request URL: `https://cms-backend-roman.vercel.app/slack/events`
- Bot events: `reaction_added`, `message.channels`

**Signing secret**: Slack app → Basic Information → App Credentials → **Signing Secret** → backend env `SLACK_SIGNING_SECRET`.

### HMAC verification

```python
import hashlib
import hmac
import time

def verify_slack_signature(timestamp: str, body: bytes, signature: str, secret: str) -> bool:
    if abs(time.time() - int(timestamp)) > 300:  # 5min replay window
        return False
    sig_basestring = f"v0:{timestamp}:{body.decode()}".encode()
    expected = "v0=" + hmac.new(secret.encode(), sig_basestring, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
```

Rejects:
- Missing `X-Slack-Request-Timestamp` or `X-Slack-Signature` → 401
- Timestamp older than 5min → 401 (replay protection)
- HMAC mismatch → 401

## Router endpoint

`backend/auth_service/routers/slack_events.py`:

```python
@router.post("/slack/events")
async def slack_events(request: Request) -> Response:
    body = await request.body()
    payload = await request.json()

    if payload.get("type") == "url_verification":
        return Response(content=payload["challenge"], media_type="text/plain")

    ts = request.headers.get("x-slack-request-timestamp", "")
    sig = request.headers.get("x-slack-signature", "")
    if not verify_slack_signature(ts, body, sig, settings.SLACK_SIGNING_SECRET):
        return Response(status_code=status.HTTP_401_UNAUTHORIZED)

    event_id = payload.get("event_id")
    if event_id and already_processed(event_id):
        return Response(status_code=status.HTTP_200_OK)
    mark_processed(event_id)

    event = payload.get("event", {})
    event_type = event.get("type")

    if event_type == "reaction_added":
        slack_handler.handle_reaction_added(event)
    elif event_type == "message":
        slack_handler.handle_message(event)

    return Response(status_code=status.HTTP_200_OK)
```

No `require_user` — authenticated via HMAC. Returns 200 except on bad signature.

## Reaction handler — approve flow

```python
def handle_reaction_added(event: dict) -> None:
    if event.get("reaction") != "white_check_mark":
        return

    item = event.get("item", {})
    if item.get("type") != "message":
        return
    msg_ts = item.get("ts")
    channel = item.get("channel")
    if not msg_ts or channel != settings.SLACK_ISSUES_CHANNEL_ID:
        return

    issue = _find_issue_by_slack_ts(msg_ts)
    if not issue:
        return

    if event.get("user") != settings.SLACK_APPROVER_USER_ID:
        _post_thread_reply(msg_ts, "⚠️ Only Stefan can approve. Reaction ignored.")
        return

    if issue["status"] != "done":
        _post_thread_reply(msg_ts, f"⚠️ Issue is `{issue['status']}` — cannot approve.")
        return

    project = _get_project_full(issue["project_id"])

    try:
        merge_result = github_merge.fast_forward(
            repo=project["github_repo"],
            base_branch=project["production_branch"],
            head_branch=project["repo_branch"],
        )
    except github_merge.GitHubError as e:
        _post_thread_reply(msg_ts, f"❌ Production merge failed: {e}")
        return

    try:
        issue_resolved_email.send(
            to_email=_email_for_user(issue["created_by"]),
            issue=issue,
            project=project,
        )
    except Exception:
        logger.exception("client email failed")
        _post_thread_reply(
            msg_ts,
            f"⚠️ Merged to `{project['production_branch']}` but email failed. "
            f"Notify client manually. Deployment: {project.get('production_url') or '(unknown)'}"
        )
        return

    _clear_revision_feedback(issue["id"])

    _post_thread_reply(
        msg_ts,
        f"🚀 *Promoted to production.*\n"
        f"• Merged `{project['repo_branch']}` → `{project['production_branch']}` "
        f"(SHA `{merge_result['object']['sha'][:7]}`)\n"
        f"• Email sent to client\n"
        f"• Production: {project.get('production_url') or '(deploy in progress)'}"
    )
```

Reactor must equal `SLACK_APPROVER_USER_ID` — prevents non-Stefan workspace members from triggering production deploys. Only `:white_check_mark:` (✅) triggers; other reactions ignored silently.

## Message handler — revision flow

```python
def handle_message(event: dict) -> None:
    if event.get("subtype") == "bot_message":
        return
    if event.get("bot_id") or event.get("user") == settings.SLACK_BOT_USER_ID:
        return

    channel = event.get("channel")
    thread_ts = event.get("thread_ts")
    text = event.get("text", "").strip()

    if channel != settings.SLACK_ISSUES_CHANNEL_ID or not thread_ts:
        return

    issue = _find_issue_by_slack_ts(thread_ts)
    if not issue:
        return

    if event.get("user") != settings.SLACK_APPROVER_USER_ID:
        return

    if issue["status"] != "done":
        _post_thread_reply(
            thread_ts,
            f"⚠️ Issue is `{issue['status']}` — cannot mark as needs revision."
        )
        return

    if len(text) < 5:
        return

    sb = get_supabase_admin()
    sb.table("project_issues").update({
        "status": "in_progress",
        "revision_feedback": text,
        "revision_feedback_at": datetime.now(UTC).isoformat(),
    }).eq("id", issue["id"]).execute()

    excerpt = text[:120] + ("…" if len(text) > 120 else "")
    _post_thread_reply(
        thread_ts,
        f"📝 *Marked as needs revision.*\n> {excerpt}\n\n"
        f"Issue moved back to `in_progress`. Fix on `cms-preview` "
        f"and mark done again to re-trigger approval."
    )
```

Bot's own messages are filtered to prevent feedback loops. Only Stefan's text counts as revision; other workspace members can chat in the thread without effect. Minimum 5 chars guards against emoji-only or accidental replies.

## GitHub merge service

`backend/auth_service/services/github_merge.py`

```python
class GitHubError(Exception):
    pass


def fast_forward(*, repo: str, base_branch: str, head_branch: str) -> dict:
    """Update base_branch ref to head of head_branch.

    repo is "owner/name". Returns the GitHub API response.
    Raises GitHubError on any non-2xx.
    """
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise GitHubError("GITHUB_TOKEN not configured")

    head = _get(f"https://api.github.com/repos/{repo}/git/refs/heads/{head_branch}", token)
    new_sha = head["object"]["sha"]

    body = json.dumps({"sha": new_sha, "force": False}).encode()
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/git/refs/heads/{base_branch}",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "cms-backend/1.0",
        },
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()
        if e.code == 422:
            raise GitHubError(
                f"Cannot fast-forward {base_branch} to {head_branch} — diverged. "
                f"Resolve manually. ({body_text})"
            ) from e
        raise GitHubError(f"GitHub {e.code}: {body_text}") from e
```

`force: False`: if branches diverged, GitHub returns 422 → surfaced as Slack failure → Stefan resolves manually. Prevents accidental commit loss.

`GITHUB_TOKEN` scope: `repo` (contents write). Reuses the PAT CMS Connector agent uses.

## Resend email service

`backend/auth_service/services/issue_resolved_email.py`

Inline HTML matching the `project_request_email.py` header pattern: black `#18181b` bar, `https://roman-technologies.dev/logo_dark.png` logo, "Roman Technologies / Client Portal" eyebrow text. Body has:

- H1: "Your issue is fixed."
- Greeting with client's name
- Issue title + description in a `#fafafa` boxed section
- CTA button → `production_url`
- Footer with copyright + portal link

Skips for E2E throwaway emails via existing `e2e_email_guard`. Raises `RuntimeError` if `RESEND_API_KEY` unset or Resend returns non-2xx.

All caller-controlled fields HTML-escaped. `production_url` validated as http(s) before injecting into href; falls back to `https://roman-technologies.dev` otherwise (matches `welcome_email._safe_url` pattern).

## Configuration

### New env vars

| Var | Source | Notes |
|---|---|---|
| `SLACK_SIGNING_SECRET` | Slack app → Basic Information | required for HMAC; disabled mode unavailable here (router refuses signed requests if unset) |
| `SLACK_APPROVER_USER_ID` | Stefan's Slack member ID (`U...`) | pinned approver identity |
| `SLACK_BOT_USER_ID` | Slack app → OAuth & Permissions | self-loop guard in message handler |
| `GITHUB_TOKEN` | reuse CMS Connector PAT or create new (`repo` scope) | needed for fast-forward merge |
| `SLACK_BOT_TOKEN` | already exists, **rotate** after adding new scopes | xoxb token, gets new value after re-install |

### Slack app re-install steps

1. https://api.slack.com/apps → CMS Issues Bot → **OAuth & Permissions** → add `reactions:read`, `channels:history` → click **Reinstall to Workspace** → approve → copy new `xoxb-...`.
2. **Basic Information** → copy **Signing Secret** into `SLACK_SIGNING_SECRET`.
3. **Event Subscriptions** → toggle Enable → Request URL: `https://cms-backend-roman.vercel.app/slack/events` (Slack will verify by POSTing a challenge — endpoint must already be deployed). → Subscribe to bot events: `reaction_added`, `message.channels` → Save.

### Deploy ordering (avoid partial-state failures)

1. Apply DB migration (`slack_inbound_s1_5.sql`) — adds columns + idempotency table + UPDATE on `repo_branch`. Backwards-compatible.
2. Set all Vercel envs (preview + production) including rotated `SLACK_BOT_TOKEN`.
3. Merge PR → backend deploys.
4. Save event subscription URL in Slack dashboard — Slack pings, gets challenge response, enables delivery.
5. Smoke test in production.

## Error handling

| Stage | Failure | Behavior |
|---|---|---|
| HMAC verify | bad signature, missing headers, replay | 401 immediately; payload not logged |
| Idempotency check | DB error | log + dispatch anyway (merge is idempotent; email may double-send) |
| Issue lookup | `slack_resolved_ts` not found | log + 200; reaction on random message |
| Reactor identity | not Stefan | Slack thread warning + return |
| Issue state | not `done` | Slack thread warning + return |
| GitHub 422 | diverged branches | Slack thread reply with manual-resolve instructions |
| GitHub other | network / 401 / 404 | Slack thread reply with raw error |
| Resend email | any failure | Slack thread: "merged but email failed, notify manually" |
| Slack ack post | Slack API failure | log only; action succeeded |
| Revision msg < 5 chars | silent ignore |
| Revision msg from bot | silent ignore (loop prevention) |

**Invariants:**
- HMAC must succeed before any payload work.
- GitHub merge failure leaves issue in `done` state (no rollback needed).
- Email failure happens after merge; production already deployed — Slack thread tells Stefan to notify client manually.

## Testing

### Unit — HMAC verifier (`tests/test_slack_signature.py`)
- Valid signature → True
- Wrong signature → False
- Expired timestamp (>5min old) → False
- Missing fields → False

### Unit — `handle_reaction_added` (`tests/test_slack_handler.py`)
- Wrong emoji → no-op
- Wrong channel → no-op
- Unknown msg_ts → no-op
- Wrong reactor → posts warning, no merge
- Issue not `done` → posts warning, no merge
- Happy path → merge + email + ack
- GitHub diverged → Slack failure message
- Email failure → "merged but email failed" message

### Unit — `handle_message`
- Bot's own message → no-op
- Top-level message (no thread_ts) → no-op
- Unknown thread → no-op
- Wrong user → no-op
- Status not done → warning, no state change
- Text < 5 chars → no-op
- Happy path → status flips, feedback stored, ack posted

### Unit — `github_merge.fast_forward`
- Mock urllib, assert PATCH body shape
- 422 → `GitHubError`
- 404 → `GitHubError`
- Network exception → `GitHubError`

### Unit — `issue_resolved_email`
- Disabled (no `RESEND_API_KEY`) → RuntimeError
- E2E guard short-circuit
- HTML escaping in title/description
- `production_url` non-http(s) → falls back to default

### Integration — `POST /slack/events`
- url_verification challenge → returns challenge text, 200
- Bad signature → 401
- Valid + reaction_added → `handle_reaction_added` called (mocked)
- Valid + message → `handle_message` called (mocked)
- Duplicate event_id → 200, no re-dispatch

### Manual E2E (post-deploy)
1. Submit issue → mark done → resolved Slack message.
2. ✅ react → expect "🚀 Promoted to production" in thread within 5s, GitHub `master` updated to `cms-preview` HEAD, Resend email in client inbox.
3. Submit another issue, mark done, reply "needs change: copy is wrong" in thread → expect "📝 Marked as needs revision", issue back to `in_progress`, `revision_feedback` column populated, **no email** sent.

## Out of scope (deferred)

- Rate limiting on `/slack/events` (Slack itself caps event delivery; revisit if abuse seen)
- pg_cron sweep of `slack_processed_events` rows older than 1 hour
- Per-project approvers (single approver = Stefan)
- Email retry on transient Resend failures
- Solver agent invocation in revise_issue (S3 territory — text reply only stores feedback today)
- Approval notification email to Stefan himself (he already sees Slack ack)
- Slack `views.open` modal for richer rejection forms

## Success criteria

- Stefan ✅ on a resolved-issue Slack message → within 5s: GitHub `master` ref updated, Slack thread shows "🚀 Promoted to production", Resend email delivered to client inbox, `revision_feedback` cleared.
- Stefan replies "<feedback text>" in the resolved-message thread → within 2s: issue status flips to `in_progress`, `revision_feedback` populated with the text, Slack thread shows "📝 Marked as needs revision".
- Non-Stefan reactor → no production deploy, Slack warning posted.
- HMAC failure → 401 with no payload echoed.
- Duplicate Slack event delivery → second delivery is a no-op.
- All new unit + integration tests pass in CI.
- S1 outbound notifications still work (no regression).

## Open questions

None — all resolved during brainstorm.
