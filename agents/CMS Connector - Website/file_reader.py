"""
file_reader.py — Walks a client website directory and returns the source files
most likely to contain hard-coded content that should be managed by the CMS.
"""

from __future__ import annotations

import os
from pathlib import Path

INCLUDE_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx", ".vue", ".svelte", ".astro"}

# Sub-paths that are likely to contain content (checked with 'in path')
PRIORITY_DIRS = {"constants", "data", "content", "config", "views", "pages", "sections"}

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


def _priority_score(rel_path: str) -> int:
    """Higher score = read this file first."""
    score = 0
    lower = rel_path.lower()
    for d in PRIORITY_DIRS:
        if d in lower:
            score += 2
    # Types and data files are gold
    if "types" in lower or "type" in lower:
        score += 1
    # Views / components that render content
    if any(k in lower for k in ("view", "page", "section", "hero", "about", "contact")):
        score += 1
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
