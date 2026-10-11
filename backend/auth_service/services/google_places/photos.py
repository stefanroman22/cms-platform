"""Copy a listing's photos into the public `lead-photos` bucket (ADR-0012).

Photo resource names expire, so the image bytes are fetched now and the name is kept
only as provenance. Each photo keeps its author attribution; `owner_photo` marks the
ones the business itself uploaded (attribution name == business name)."""

from __future__ import annotations

import hashlib
import logging
import posixpath
import urllib.parse

from . import client
from .mapper import normalize_name

logger = logging.getLogger(__name__)

BUCKET = "lead-photos"
_EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
_PUBLIC_MARKER = f"/storage/v1/object/public/{BUCKET}/"


def is_owner_photo(business_name: str, attributions: list[dict]) -> bool:
    target = normalize_name(business_name)
    return any(normalize_name(a.get("name") or "") == target for a in attributions if a.get("name"))


def storage_path_of(url: str) -> str | None:
    """'…/object/public/lead-photos/<path>' -> '<path>' (query stripped), else None."""
    path = urllib.parse.urlsplit(url).path
    if _PUBLIC_MARKER not in path:
        return None
    decoded = urllib.parse.unquote(path.split(_PUBLIC_MARKER, 1)[1])
    if not decoded:
        return None
    if posixpath.normpath(decoded) != decoded or any(
        seg in ("", "..") for seg in decoded.split("/")
    ):
        return None
    return decoded


def download_photos(
    sb,
    lead_id: str,
    business_name: str,
    photos: list[dict],
    *,
    max_photos: int,
    max_width_px: int = 1600,
) -> tuple[list[str], list[dict], list[str]]:
    store = sb.storage.from_(BUCKET)
    urls: list[str] = []
    meta: list[dict] = []
    warnings: list[str] = []
    for index, photo in enumerate(photos[: max(0, max_photos)]):
        name = photo.get("name") or ""
        try:
            uri = client.photo_uri(name, max_width_px=max_width_px)
            body, ctype = client.fetch_bytes(uri)
        except client.GooglePlacesError as e:
            warnings.append(f"photo {name} skipped: {e.message}")
            continue
        ext = _EXT.get(ctype)
        if ext is None:
            warnings.append(f"photo {name} skipped: unsupported content type {ctype or 'unknown'}")
            continue
        digest = hashlib.sha1(body).hexdigest()[:10]
        path = f"{lead_id}/{index:02d}-{digest}{ext}"
        try:
            store.upload(
                path=path, file=body, file_options={"content-type": ctype, "upsert": "true"}
            )
            url = store.get_public_url(path)
        except Exception as e:  # noqa: BLE001 — storage hiccup must not fail the import
            logger.exception("lead photo upload failed (%s)", path)
            warnings.append(f"photo {name} skipped: upload failed ({type(e).__name__})")
            continue
        urls.append(url)
        meta.append(
            {
                **photo,
                "storage_path": path,
                "url": url,
                "owner_photo": is_owner_photo(business_name, photo.get("attributions") or []),
            }
        )
    return urls, meta, warnings


def delete_lead_photos(sb, lead_id: str, urls: list[str] | None = None) -> list[str]:
    store = sb.storage.from_(BUCKET)
    if urls is None:
        paths = [
            f"{lead_id}/{f['name']}"
            for f in (store.list(lead_id, {"limit": 1000}) or [])
            if f.get("id")
        ]
    else:
        paths = [p for p in (storage_path_of(u) for u in urls) if p and p.startswith(f"{lead_id}/")]
    if paths:
        store.remove(paths)
    return paths
