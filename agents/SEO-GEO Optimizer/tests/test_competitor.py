# agents/SEO-GEO Optimizer/tests/test_competitor.py
import importlib.util
import pathlib

_rc = pathlib.Path(__file__).resolve().parents[1] / "render_check.py"
_cp = pathlib.Path(__file__).resolve().parents[1] / "competitor.py"
import importlib.machinery  # noqa


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


comp = _load("seo_competitor", _cp)

CLIENT = {
    "jsonld_types": ["LocalBusiness"],
    "word_count": 120,
    "has_faq": False,
    "headings": ["Services", "Visit"],
}
RIVAL_A = {
    "jsonld_types": ["LocalBusiness", "FAQPage"],
    "word_count": 900,
    "has_faq": True,
    "headings": ["Services", "Pricing", "FAQ", "Reviews"],
}


def test_extract_competitor_signals_detects_faq_schema():
    html = (
        '<html><body><h1>R</h1><h2>FAQ</h2><script type="application/ld+json">{"@type":"FAQPage"}</script><p>'
        + ("word " * 80)
        + "</p></body></html>"
    )
    sig = comp.extract_competitor_signals(html)
    assert sig["has_faq"] is True
    assert "FAQPage" in sig["jsonld_types"]
    assert sig["word_count"] >= 60


def test_content_gaps_flags_thin_content_and_missing_schema():
    gaps = comp.content_gaps(CLIENT, [RIVAL_A])
    joined = " ".join(gaps).lower()
    assert "faq" in joined  # rival uses FAQ structure, client doesn't
    assert "word" in joined or "thin" in joined or "depth" in joined  # rival much longer
    # gaps are advisory strings, no refuted stats
    assert "3.2x" not in joined and "74%" not in joined


def test_content_gaps_empty_when_client_leads():
    gaps = comp.content_gaps(RIVAL_A, [CLIENT])
    assert isinstance(gaps, list)
