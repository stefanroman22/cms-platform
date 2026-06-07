"""Tests for the per-country region registry."""

from __future__ import annotations

import pytest

from scraper.regions import RegionEntry, list_countries, load_country


def _write(tmp_path, cc, lines):
    p = tmp_path / f"{cc}.jsonl"
    p.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
    return p


def test_load_country_reads_jsonl(tmp_path):
    _write(
        tmp_path,
        "xx",
        [
            '{"name":"Foo","country_code":"XX","code":"C1","bbox":[52.0,5.0,52.1,5.1]}',
            '{"name":"Bar","country_code":"XX","code":"C2","bbox":[51.0,4.0,51.1,4.1]}',
        ],
    )
    entries = load_country("XX", base_dir=tmp_path)
    assert [e.name for e in entries] == ["Foo", "Bar"]
    assert entries[0].bbox == (52.0, 5.0, 52.1, 5.1)
    assert isinstance(entries[0], RegionEntry)


def test_load_country_skips_blank_lines(tmp_path):
    _write(tmp_path, "xx", ['{"name":"A","country_code":"XX","bbox":[1.0,2.0,3.0,4.0]}', "", "  "])
    assert len(load_country("xx", base_dir=tmp_path)) == 1


def test_load_country_unknown_raises(tmp_path):
    with pytest.raises(ValueError, match="no region file"):
        load_country("zz", base_dir=tmp_path)


def test_list_countries(tmp_path):
    _write(tmp_path, "nl", [])
    _write(tmp_path, "de", [])
    assert set(list_countries(base_dir=tmp_path)) == {"nl", "de"}


def test_list_countries_includes_nl_real():
    # Default base_dir → the packaged registry dir; locks the shipped nl.jsonl in.
    assert "nl" in list_countries()


def test_load_country_nl_has_342_municipalities():
    entries = load_country("nl")
    assert len(entries) == 342
    names = {e.name for e in entries}
    assert "Amsterdam" in names and "Rotterdam" in names
    for e in entries:
        min_lat, min_lng, max_lat, max_lng = e.bbox
        assert min_lat < max_lat and min_lng < max_lng
        assert 50.0 <= min_lat <= 54.0 and 3.0 <= min_lng <= 7.5  # NL range
