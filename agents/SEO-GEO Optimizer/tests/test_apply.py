# agents/SEO-GEO Optimizer/tests/test_apply.py
import importlib.util
import pathlib

_p = pathlib.Path(__file__).resolve().parents[1] / "apply.py"
_spec = importlib.util.spec_from_file_location("seo_apply", _p)
apply = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(apply)


def test_page_meta_payload_defaults_to_draft():
    p = apply.build_page_meta_payload("pid", "/", "en", {"title": "Home", "description": "d"})
    assert p["project_id"] == "pid" and p["route"] == "/" and p["locale"] == "en"
    assert p["title"] == "Home" and p["status"] == "draft" and p["updated_by"] == "agent"


def test_article_payload_carries_run_and_draft():
    p = apply.build_article_payload(
        "pid", "run1", "guide-fades", "nl", {"title": "Gids", "body": "x", "excerpt": "e"}
    )
    assert p["slug"] == "guide-fades" and p["locale"] == "nl"
    assert p["status"] == "draft" and p["source_run_id"] == "run1" and p["updated_by"] == "agent"


def test_diff_before_after_lists_changed_fields_only():
    d = apply.diff_before_after(
        {"title": "Old", "description": "same"}, {"title": "New", "description": "same"}
    )
    assert d == {"title": {"before": "Old", "after": "New"}}


def test_diff_handles_added_field():
    d = apply.diff_before_after({}, {"title": "New"})
    assert d == {"title": {"before": None, "after": "New"}}


# ---- SEC-057: parameter-safe competitor persistence ----


def test_sql_str_escapes_single_quote():
    # An everyday apostrophe is doubled — the row still stores the real text.
    assert apply.sql_str("O'Brien's Barbers") == "'O''Brien''s Barbers'"


def test_sql_str_none_is_empty_literal():
    assert apply.sql_str(None) == "''"


def test_build_competitor_insert_sql_neutralises_injection():
    # A classic stacked-statement payload planted in the competitor NAME.
    evil = "x','',now()); UPDATE projects SET owner_id='attacker' WHERE slug='victim'; --"
    payload = apply.build_competitor_payload(
        project_id="proj-1",
        run_id="run-1",
        name=evil,
        url="https://evil.example",
        location="Rotterdam",
        signals={"has_faq": True},
        analysis="ok",
    )
    sql = apply.build_competitor_insert_sql(payload)
    # Core invariant: every quote in the payload is doubled, so the name survives ONLY
    # as one inert string literal — it can never close the literal early.
    assert apply.sql_str(evil) == "'" + evil.replace("'", "''") + "'"
    assert apply.sql_str(evil) in sql  # the whole payload sits inside a single literal
    # After collapsing the escaped `''` pairs, the remaining single quotes are just the
    # literal delimiters and must be balanced — proof no stray quote broke a literal open.
    assert sql.replace("''", "").count("'") % 2 == 0
    # The `UPDATE projects ... ; --` text is present but inert (inside the name literal).
    assert "UPDATE projects" in sql


def test_build_competitor_insert_sql_signals_is_valid_jsonb_literal():
    payload = apply.build_competitor_payload(
        "p", "r", "Acme", "https://a", "Delft", {"word_count": 900}, "analysis"
    )
    sql = apply.build_competitor_insert_sql(payload)
    assert "'{\"word_count\": 900}'::jsonb" in sql
    assert sql.startswith(
        "INSERT INTO seo_competitors (project_id, run_id, name, url, location, "
        "signals, analysis, captured_at) VALUES ("
    )
