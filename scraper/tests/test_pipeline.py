from collections.abc import AsyncIterator

import pytest

from scraper.models import Lead, ScrapeParams
from scraper.pipeline import Counters, run_pipeline
from scraper.sinks.base import Sink


class _FakeSink(Sink):
    def __init__(self, fail_on: set[str] | None = None) -> None:
        self.opened = False
        self.closed = False
        self.written: list[Lead] = []
        self._fail = fail_on or set()

    async def open(self) -> None:
        self.opened = True

    async def write(self, lead: Lead) -> bool:
        if lead.external_id in self._fail:
            return False
        self.written.append(lead)
        return True

    async def close(self) -> None:
        self.closed = True


async def _fake_scrape(
    params: ScrapeParams, scrape_job_id: str | None = None
) -> AsyncIterator[Lead]:
    for eid in ("a", "b", "c"):
        yield Lead(external_id=eid, business_name=eid, name_normalized=eid)


@pytest.mark.asyncio
async def test_pipeline_writes_to_all_sinks_and_counts(monkeypatch):
    monkeypatch.setattr("scraper.pipeline._scrape", _fake_scrape)
    s1, s2 = _FakeSink(), _FakeSink(fail_on={"b"})

    counters = await run_pipeline(ScrapeParams(category="x", country="NL"), [s1, s2])

    assert counters.found == 3
    assert counters.inserted == 3
    assert counters.skipped == 1
    assert s1.opened and s1.closed
    assert s2.opened and s2.closed
    assert {lead.external_id for lead in s1.written} == {"a", "b", "c"}
    assert {lead.external_id for lead in s2.written} == {"a", "c"}


@pytest.mark.asyncio
async def test_pipeline_closes_sinks_on_scrape_failure(monkeypatch):
    """Even if scrape iteration raises, sinks must close."""

    async def boom_scrape(params, scrape_job_id=None):
        yield Lead(external_id="a", business_name="x", name_normalized="x")
        raise RuntimeError("upstream blew up")

    monkeypatch.setattr("scraper.pipeline._scrape", boom_scrape)
    s = _FakeSink()
    with pytest.raises(RuntimeError, match="upstream"):
        await run_pipeline(ScrapeParams(category="x", country="NL"), [s])
    assert s.opened
    assert s.closed


@pytest.mark.asyncio
async def test_pipeline_counters_default():
    c = Counters()
    assert c.found == 0 and c.inserted == 0 and c.skipped == 0
