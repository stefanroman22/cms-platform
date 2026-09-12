# agents/SEO-GEO Optimizer/tests/test_sql_safe.py
"""SEC-061: the SQL-literal escaping primitive the agent must use before
interpolating scraped/LLM values into execute_sql queries."""

import importlib.util
import pathlib

import pytest

_ss = pathlib.Path(__file__).resolve().parents[1] / "sql_safe.py"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sql_safe = _load("seo_sql_safe", _ss)


def test_plain_value_is_quoted():
    assert sql_safe.literal("Bob Barbers") == "'Bob Barbers'"


def test_apostrophe_is_doubled():
    # A legitimate name with an apostrophe must not break the literal.
    assert sql_safe.literal("Bob's Barbers") == "'Bob''s Barbers'"


def test_none_is_sql_null():
    assert sql_safe.literal(None) == "NULL"


def test_non_string_scalar_is_coerced():
    assert sql_safe.literal(42) == "'42'"


def test_injection_payload_is_neutralized():
    # The canonical breakout: close the literal, run a second statement.
    payload = "x','y'); DROP TABLE seo_competitors; --"
    lit = sql_safe.literal(payload)
    # Every single quote in the payload is doubled, so the literal stays closed:
    # the whole payload is a single quoted string, not two statements.
    assert lit == "'x'',''y''); DROP TABLE seo_competitors; --'"
    # The rendered literal has exactly one opening + one closing quote at the ends
    # and only doubled quotes inside — no lone quote can terminate it early.
    inner = lit[1:-1]
    assert "'" not in inner.replace("''", "")


def test_nul_byte_is_rejected():
    with pytest.raises(sql_safe.UnsafeSQLValueError):
        sql_safe.literal("bad\x00value")


def test_json_literal_serializes_and_casts():
    out = sql_safe.json_literal({"jsonld_types": ["LocalBusiness"], "has_faq": True})
    assert out.endswith("::jsonb")
    assert out.startswith("'")
    # Round-trips back to the original object after stripping the quotes/cast.
    import json

    body = out[: -len("::jsonb")]
    assert body[0] == "'" and body[-1] == "'"
    decoded = json.loads(body[1:-1].replace("''", "'"))
    assert decoded == {"jsonld_types": ["LocalBusiness"], "has_faq": True}


def test_json_literal_escapes_embedded_quote_from_scraped_data():
    # A scraped heading with a single quote must survive JSON + SQL escaping.
    out = sql_safe.json_literal({"headings": ["We're the best'); DROP"]})
    # No lone single quote can terminate the SQL literal early.
    inner = out[1 : out.rindex("'")]
    assert "'" not in inner.replace("''", "")
