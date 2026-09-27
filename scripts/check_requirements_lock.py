"""Guardrail L2: every pin in a requirements*.txt must match its hashed .lock.

Vercel installs requirements.txt, but the promote gate installs requirements.lock with
--require-hashes, so drift means production runs versions the gate never checked.
Fix a failure by regenerating the lock (command is in the lock file's header).
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAIRS = [
    "backend/requirements",
    "backend/requirements-dev",
    "agents/CMS Connector - Website/requirements",
    "agents/CMS Connector - Website/requirements-dev",
]
REQ = re.compile(
    r"^([A-Za-z0-9][A-Za-z0-9._-]*)(\[[^\]]*\])?\s*(==|>=|<=|~=|!=|>|<)?\s*([^\s;#\\]*)"
)


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def parse(path: Path) -> dict[str, tuple[str, str]]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        m = REQ.match(line)
        if m:
            out[norm(m.group(1))] = (m.group(3) or "", m.group(4))
    return out


def main() -> int:
    problems = []
    for base in PAIRS:
        txt, lock = ROOT / f"{base}.txt", ROOT / f"{base}.lock"
        if not txt.exists() or not lock.exists():
            continue
        locked = parse(lock)
        for name, (op, ver) in parse(txt).items():
            if name not in locked:
                problems.append(f"{txt.relative_to(ROOT)}: {name} is missing from {lock.name}")
            elif op == "==" and locked[name][1] != ver:
                problems.append(
                    f"{txt.relative_to(ROOT)}: {name}=={ver} but {lock.name} has {locked[name][1]}"
                )
    for p in problems:
        print(p)
    if problems:
        print("Regenerate the lock with the pip-compile command in its header.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
