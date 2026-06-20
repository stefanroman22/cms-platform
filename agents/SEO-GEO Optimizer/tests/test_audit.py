# agents/SEO-GEO Optimizer/tests/test_audit.py
import importlib.util
import pathlib

_p = pathlib.Path(__file__).resolve().parents[1] / "audit.py"
_spec = importlib.util.spec_from_file_location("seo_audit", _p)
audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)

PERFECT = {
    "h1_count": 1,
    "heading_order_ok": True,
    "title_len": 55,
    "meta_desc_len": 150,
    "canonical": "https://x/",
    "jsonld_types": ["LocalBusiness"],
    "jsonld_valid": True,
    "has_localbusiness": True,
    "og_present": True,
    "internal_link_count": 5,
    "has_main_content": True,
    "word_count": 400,
}
EMPTY = {
    "h1_count": 0,
    "heading_order_ok": True,
    "title_len": 0,
    "meta_desc_len": 0,
    "canonical": None,
    "jsonld_types": [],
    "jsonld_valid": True,
    "has_localbusiness": False,
    "og_present": False,
    "internal_link_count": 0,
    "has_main_content": False,
    "word_count": 0,
}


def test_perfect_page_scores_high():
    score, detail = audit.score_seo(PERFECT)
    assert score >= 90
    assert detail["G-1_content_in_raw_html"] == "pass"


def test_empty_page_scores_low():
    score, _ = audit.score_seo(EMPTY)
    assert score <= 20


def test_local_score_rewards_localbusiness_jsonld():
    hi, _ = audit.score_local(PERFECT)
    lo, _ = audit.score_local(EMPTY)
    assert hi > lo and hi >= 50


def test_assemble_audit_clamps_and_carries_geo():
    a = audit.assemble_audit(seo=88, geo=72, local=64, scores_detail={"x": 1})
    assert a == {"seo_score": 88, "geo_score": 72, "local_score": 64, "scores_detail": {"x": 1}}
    # geo is provided by the LLM judge; assemble just packages it
    clamped = audit.assemble_audit(seo=120, geo=-5, local=64, scores_detail={})
    assert clamped["seo_score"] == 100 and clamped["geo_score"] == 0
