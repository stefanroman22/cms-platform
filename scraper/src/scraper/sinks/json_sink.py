"""Local dry-run output."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..models import Lead
from .base import Sink


class JsonSink(Sink):
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._rows: list[dict[str, Any]] = []
        self._seen: set[str] = set()

    async def open(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    async def write(self, lead: Lead) -> bool:
        if lead.external_id in self._seen:
            return False
        self._seen.add(lead.external_id)
        self._rows.append(lead.model_dump())
        return True

    async def close(self) -> None:
        self.path.write_text(json.dumps(self._rows, indent=2, default=str))
