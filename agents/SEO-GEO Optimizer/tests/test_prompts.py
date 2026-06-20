# agents/SEO-GEO Optimizer/tests/test_prompts.py
import importlib.util
import pathlib

_p = pathlib.Path(__file__).resolve().parents[1] / "prompts.py"
_spec = importlib.util.spec_from_file_location("seo_prompts", _p)
prompts = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prompts)


def test_all_eleven_refuted_claims_are_forbidden():
    needles = [
        "FAQPage",
        "3.2",  # FAQ 3.2x AI Overviews
        "67%",  # answer-first 67%
        "92.36",  # 92.36% top-10
        "llms.txt",  # llms.txt as signal
        "32%",  # GBP 32% weight
        "7x",
        "4.4x",  # completeness/review click multipliers
        "74%",  # NAP 74% exclusion
        "10 ",
        "categor",  # all-10-GBP-categories
        "vector",  # vector-store memory split
    ]
    blob = prompts.FORBIDDEN_CLAIMS.lower()
    for n in needles:
        assert n.lower() in blob, f"forbidden block missing reference to {n!r}"


def test_geo_judge_prompt_demands_verbatim_source_and_no_fabrication():
    p = prompts.GEO_JUDGE_PROMPT.lower()
    assert "verbatim" in p or "literal" in p
    assert "fabricat" in p or "made up" in p or "real" in p
    assert "readiness" in p  # we score readiness, never promise citation


def test_planner_prompt_uses_action_kinds():
    for kind in ["content", "meta", "schema", "article", "new_page", "manual_human"]:
        assert kind in prompts.PLANNER_PROMPT
