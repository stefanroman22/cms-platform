"""docs-check: fail when agent-facing docs reference paths or commands that no longer exist.

Guards CLAUDE.md, RUN.md, docs/decisions/*.md and security/RUNBOOK.md, plus agent guidance
(agents/*/AGENTS.md, agents/*/phases/*.md, .claude/skills/*/SKILL.md) in failures-only mode:
agent docs describe files inside the websites they generate, so their unmatched short paths are
not reported. Checks:
  - `make <target>` and `npm run <script>` in code spans / code blocks exist;
  - relative markdown links resolve;
  - paths rooted at a real top-level folder exist on disk (git-ignored paths are skipped);
  - short paths (e.g. `routers/deps.py`) match some file in the repo, else only WARN.
URLs, API routes, branch names, npm package names and placeholders are ignored, as are
table rows marked REMOVED and any line containing `<!-- docs-check: ignore -->`.
"""

import json
import os
import re
import shlex
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
DOCS = [
    ROOT / "CLAUDE.md",
    ROOT / "RUN.md",
    *sorted((ROOT / "docs/decisions").glob("*.md")),
    ROOT / "security/RUNBOOK.md",
]
AGENT_DOCS = [
    *sorted(ROOT.glob("agents/*/AGENTS.md")),
    *sorted(ROOT.glob("agents/*/phases/*.md")),
    *sorted(ROOT.glob(".claude/skills/*/SKILL.md")),
]
NPM_MANIFESTS = ["frontend/package.json", "e2e/package.json"]
SKIP_DIRS = {"node_modules", "venv", ".venv", ".git", ".next", "__pycache__", "worktrees"}
IGNORE_MARK = "<!-- docs-check: ignore -->"

PLACEHOLDER = re.compile(r"<[^>]*>|\{[^}]*\}|YYYY|…|\.\.\.")
FILE_EXT = re.compile(r"\.(py|ts|tsx|js|mjs|cjs|md|sql|json|toml|ya?ml|txt|lock|sh|css|html)$")
BRANCH = re.compile(r"^(feat|fix|chore|perf|docs|sec|origin|refs)/")
MIME = re.compile(r"^(image|video|audio|application|text|font|multipart)/")


def repo_files() -> list[str]:
    out = []
    for d, dirs, fs in os.walk(ROOT):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        rel = Path(d).relative_to(ROOT).as_posix()
        prefix = "" if rel == "." else rel + "/"
        if prefix:
            out.append(prefix.rstrip("/"))
        out += [prefix + f for f in fs]
    return out


def git_ignored(path: str) -> bool:
    r = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", path], capture_output=True)
    return r.returncode == 0


def looks_like_path(tok: str, packages: set[str]) -> str | None:
    t = tok.strip().rstrip(".,;:")
    if not t or " " in t or t.startswith(("/", "http", "@", "$", "~", "-")):
        return None
    if BRANCH.match(t) or MIME.match(t) or PLACEHOLDER.search(t) or t.split("/")[0] in packages:
        return None
    if "/" not in t and not FILE_EXT.search(t):
        return None
    if re.fullmatch(r"\.[A-Za-z0-9]+", t):  # bare extension like `.lock`
        return None
    return t


def main() -> int:
    files = repo_files()
    top = {p.name for p in ROOT.iterdir()}
    make_targets = set(
        re.findall(r"^([A-Za-z0-9_-]+):", (ROOT / "Makefile").read_text(encoding="utf-8"), re.M)
    )
    npm_scripts: set[str] = set()
    packages: set[str] = set()
    for manifest in NPM_MANIFESTS:
        data = json.loads((ROOT / manifest).read_text(encoding="utf-8"))
        npm_scripts |= set(data.get("scripts", {}))
        packages |= set(data.get("dependencies", {})) | set(data.get("devDependencies", {}))

    def exists(t: str) -> bool:
        p = t.rstrip("/")
        if (ROOT / p).exists() or git_ignored(p):
            return True
        if "*" in p:
            return any(fnmatch(f, p) or fnmatch(f, "*/" + p) for f in files)
        return any(f == p or f.endswith("/" + p) for f in files)

    fails: list[str] = []
    warns: list[str] = []
    for doc in DOCS + AGENT_DOCS:
        quiet = doc in AGENT_DOCS
        if not doc.exists():
            continue
        rel_doc = doc.relative_to(ROOT).as_posix()
        in_block = False
        for n, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("```"):
                in_block = not in_block
                continue
            if IGNORE_MARK in line or "REMOVED" in line:
                continue
            where = f"{rel_doc}:{n}"

            for link in re.findall(r"\]\(([^)\s]+)\)", line):
                if link.startswith(("http", "#", "mailto:")):
                    continue
                if not (doc.parent / unquote(link.split("#")[0])).exists():
                    fails.append(f"{where}: broken link {link}")

            code = [line] if in_block else re.findall(r"`([^`]+)`", line)
            for span in code:
                for m in re.finditer(r"\bmake ([A-Za-z0-9_-]+)", span):
                    if m.group(1) not in make_targets:
                        fails.append(f"{where}: unknown make target '{m.group(1)}'")
                for m in re.finditer(r"\bnpm run ([A-Za-z0-9:_-]+)", span):
                    if m.group(1) not in npm_scripts:
                        fails.append(f"{where}: unknown npm script '{m.group(1)}'")

                if " " in span and exists(span):  # a path with spaces, e.g. agent folders
                    continue
                spaced_path = (
                    " " in span
                    and span.split("/")[0] in top
                    and not re.search(r"&&|\|\||[;|=$<>\"']| -", span)
                    and not PLACEHOLDER.search(span)
                    and "*" not in span  # runtime globs, e.g. feedback/pending/*.md
                )
                if spaced_path:
                    fails.append(f"{where}: missing path {span}")
                    continue
                if " " in span:
                    try:
                        tokens = [a for a in shlex.split(span) if "/" in a and FILE_EXT.search(a)]
                    except ValueError:
                        tokens = []
                else:
                    tokens = [span]
                for tok in tokens:
                    t = looks_like_path(tok, packages)
                    if not t or exists(t):
                        continue
                    if "/" in t and t.split("/")[0] in top:
                        fails.append(f"{where}: missing path {t}")
                    elif not quiet:
                        warns.append(f"{where}: no file matches {t}")

    for w in warns:
        print(f"WARN {w}")
    for f in fails:
        print(f"FAIL {f}")
    print(f"docs-check: {len(fails)} failure(s), {len(warns)} warning(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
