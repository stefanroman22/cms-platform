"""Abstract sink — the contract every output implements."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Lead


class Sink(ABC):
    @abstractmethod
    async def open(self) -> None: ...

    @abstractmethod
    async def write(self, lead: Lead) -> bool:
        """Return True if newly inserted/updated, False if skipped (dup)."""

    @abstractmethod
    async def close(self) -> None: ...
