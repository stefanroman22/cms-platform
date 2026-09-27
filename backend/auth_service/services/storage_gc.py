"""Delete a project's uploaded files that its CMS content no longer references.

Uploads land at `{project_slug}/{service_key}/{uuid}.{ext}` and the public URL is stored in
the content. Replacing an image uploads a new file but never removed the old one, so storage
filled up with dead copies. After a publish, draft and published content are identical, so any
file under the project's prefix that no content row mentions is orphaned.

Files younger than MIN_AGE are skipped: they may have been uploaded but not saved yet. Booking
logos live under the tenant id, not the project slug, and are never touched here.
"""

import json
import logging
from datetime import UTC, datetime, timedelta

logger = logging.getLogger(__name__)

BUCKET = "cms-files"
MIN_AGE = timedelta(hours=24)


def _created_at(meta: dict) -> datetime | None:
    raw = meta.get("created_at")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None


def _files_under(store, project_slug: str) -> list[tuple[str, dict]]:
    """(path, metadata) for every file in the project's folder and its service subfolders."""
    files = []
    for item in store.list(project_slug, {"limit": 1000}) or []:
        if item.get("id") is not None:
            files.append((f"{project_slug}/{item['name']}", item))
            continue
        prefix = f"{project_slug}/{item['name']}"
        for f in store.list(prefix, {"limit": 1000}) or []:
            if f.get("id") is not None:
                files.append((f"{prefix}/{f['name']}", f))
    return files


def prune_unreferenced_uploads(sb, project_slug: str, contents: list) -> list[str]:
    """Remove the project's old files that none of `contents` references. Returns removed paths."""
    referenced = json.dumps(contents, default=str)
    store = sb.storage.from_(BUCKET)
    cutoff = datetime.now(UTC) - MIN_AGE
    stale = []
    for path, meta in _files_under(store, project_slug):
        created = _created_at(meta)
        if created is None or created > cutoff or path in referenced:
            continue
        stale.append(path)
    if stale:
        store.remove(stale)
        logger.info("storage gc: removed %d unreferenced file(s) for %s", len(stale), project_slug)
    return stale
