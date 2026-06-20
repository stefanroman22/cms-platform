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
