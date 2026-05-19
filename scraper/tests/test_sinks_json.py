import asyncio
import json
from pathlib import Path

from scraper.models import Lead
from scraper.sinks.json_sink import JsonSink


def _mk_lead(eid: str) -> Lead:
    return Lead(external_id=eid, business_name="x", name_normalized="x")


def test_json_sink_writes_array(tmp_path: Path):
    path = tmp_path / "out.json"
    sink = JsonSink(path)

    async def run() -> None:
        await sink.open()
        assert await sink.write(_mk_lead("a")) is True
        assert await sink.write(_mk_lead("b")) is True
        assert await sink.write(_mk_lead("a")) is False  # dup
        await sink.close()

    asyncio.run(run())
    data = json.loads(path.read_text())
    assert {row["external_id"] for row in data} == {"a", "b"}


def test_json_sink_handles_empty(tmp_path: Path):
    path = tmp_path / "empty.json"
    sink = JsonSink(path)

    async def run() -> None:
        await sink.open()
        await sink.close()

    asyncio.run(run())
    assert json.loads(path.read_text()) == []
