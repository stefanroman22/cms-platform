"""
file_reader.py — Walks a client website directory and returns the source files
most likely to contain hard-coded content that should be managed by the CMS.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

INCLUDE_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx", ".vue", ".svelte", ".astro", ".json"}

# Sub-paths that are likely to contain content (checked with 'in path')
PRIORITY_DIRS = {
    "constants",
    "data",
    "content",
    "config",
    "views",
    "pages",
    "sections",
    "messages",
    "locales",
    "i18n",
}

# JSON files whose names are noisy config — never treat as locale catalogs
_JSON_NOISE_NAMES = {
    "package.json",
    "package-lock.json",
    "tsconfig.json",
    "tsconfig.base.json",
    "tsconfig.node.json",
}

# Matches bare locale-code filenames like en.json, nl.json, en-GB.json, zh-Hant.json
_LOCALE_CODE_RE = re.compile(r"^[a-z]{2,3}(-[A-Za-z]{2,4})?\.json$")

# Path segments that signal a translation/i18n directory
_I18N_PATH_SEGMENTS = {"messages", "locales", "i18n"}

EXCLUDE_DIRS = {
    "node_modules",
    "dist",
    ".next",
    ".nuxt",
    ".output",
    ".git",
    "__pycache__",
    "venv",
    ".venv",
    "coverage",
    ".turbo",
    "build",
    "storybook-static",
    ".cache",
}

MAX_FILE_SIZE_BYTES = 150_000  # skip files larger than ~150 KB
MAX_FILES = 60  # hard cap — Claude context has limits


def _is_excluded(path: Path) -> bool:
    for part in path.parts:
        if part in EXCLUDE_DIRS:
            return True
    return False


def _is_locale_json(rel_path: str) -> bool:
    """
    Returns True only for .json files that are likely translation catalogs.
    Accepted when:
      - any path segment is in _I18N_PATH_SEGMENTS  (e.g. messages/en.json)
      - OR the filename alone is a locale code        (e.g. en.json, en-GB.json)
    Rejected when the filename is a known noisy config name.
    """
    fname = Path(rel_path).name
    if fname in _JSON_NOISE_NAMES:
        return False
    # Locale code pattern in filename is sufficient (covers root-level en.json etc.)
    if _LOCALE_CODE_RE.match(fname):
        return True
    # Or any segment of the path is an i18n directory
    lower_parts = {p.lower() for p in Path(rel_path).parts}
    return bool(lower_parts & _I18N_PATH_SEGMENTS)


def _priority_score(rel_path: str) -> int:
    """Higher score = read this file first."""
    score = 0
    lower = rel_path.lower()

    # .json files that are NOT locale catalogs get a large penalty so they never
    # crowd out real source files and fall below the MAX_FILES cap.
    if rel_path.endswith(".json"):
        if not _is_locale_json(rel_path):
            score -= 10
            return score
        # Locale catalogs: apply i18n boost then return
        score += 3  # base boost for being a translation file
        for seg in _I18N_PATH_SEGMENTS:
            if seg in lower:
                score += 2
        if "[locale]" in lower or "locale" in lower:
            score += 1
        return score

    for d in PRIORITY_DIRS:
        if d in lower:
            score += 2
    # Types and data files are gold
    if "types" in lower or "type" in lower:
        score += 1
    # Views / components that render content
    if any(k in lower for k in ("view", "page", "section", "hero", "about", "contact")):
        score += 1
    # i18n routing / config files
    if any(seg in lower for seg in _I18N_PATH_SEGMENTS):
        score += 3
    if "[locale]" in lower or "locale" in lower:
        score += 2
    # Deprioritise test files and config
    if any(
        k in lower
        for k in ("test", "spec", "story", "mock", ".config.", "vite", "eslint", "tailwind")
    ):
        score -= 3
    return score


def read_website_files(root: str | Path) -> dict[str, str]:
    """
    Returns {relative_path: file_contents} for the most relevant source files
    in the given client website directory.
    """
    root = Path(root).resolve()
    candidates: list[tuple[int, Path]] = []

    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)

        # Prune excluded dirs in-place so os.walk doesn't descend into them
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]

        if _is_excluded(current.relative_to(root)):
            continue

        for fname in filenames:
            fpath = current / fname
            if fpath.suffix not in INCLUDE_EXTENSIONS:
                continue
            if fpath.stat().st_size > MAX_FILE_SIZE_BYTES:
                continue
            rel = str(fpath.relative_to(root))
            score = _priority_score(rel)
            # Exclude noisy JSON that scored very low (non-locale JSON)
            if rel.endswith(".json") and score < 0:
                continue
            candidates.append((score, fpath))

    # Sort descending by priority score, then alphabetically for determinism
    candidates.sort(key=lambda t: (-t[0], str(t[1])))

    result: dict[str, str] = {}
    for _, fpath in candidates[:MAX_FILES]:
        rel = str(fpath.relative_to(root))
        try:
            result[rel] = fpath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass

    return result
