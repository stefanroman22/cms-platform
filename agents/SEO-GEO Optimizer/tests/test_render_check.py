# agents/SEO-GEO Optimizer/tests/test_render_check.py
import importlib.util
import pathlib

_p = pathlib.Path(__file__).resolve().parents[1] / "render_check.py"
_spec = importlib.util.spec_from_file_location("seo_render_check", _p)
rc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rc)

GOOD = """
<html><head>
<title>Best Barber in Rotterdam — Samir Kapsalon</title>
<meta name="description" content="Sharp fades and classic cuts in central Rotterdam. Book your barber online in under a minute at Samir Kapsalon, with walk-ins welcome and top local ratings.">
<link rel="canonical" href="https://x.nl/">
<meta property="og:title" content="Samir"><meta property="og:image" content="https://x.nl/og.png">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"LocalBusiness","name":"Samir"}</script>
</head><body>
<h1>Samir Kapsalon</h1>
<h2>Services</h2><p>We offer sharp fades, classic scissor cuts, hot-towel shaves and beard trims for every style. According to a 2025 industry survey, 70% of our clients now book their appointments online instead of waiting in line.</p>
<h2>Visit</h2><p>Find us in central Rotterdam, a short walk from the station. Walk-ins are welcome, but booking ahead guarantees your preferred barber and time slot on busy weekends.</p>
<a href="/services">Services</a><a href="/contact">Contact</a>
</body></html>
"""

BAD = "<html><head></head><body><div id='root'></div></body></html>"


def test_extract_signals_good_page():
    s = rc.extract_signals(GOOD)
    assert s["h1_count"] == 1
    assert s["heading_order_ok"] is True
    assert 40 <= s["title_len"] <= 60
    assert 140 <= s["meta_desc_len"] <= 160
    assert s["canonical"] == "https://x.nl/"
    assert "LocalBusiness" in s["jsonld_types"]
    assert s["jsonld_valid"] is True
    assert s["has_localbusiness"] is True
    assert s["og_present"] is True
    assert s["internal_link_count"] == 2
    assert s["has_main_content"] is True
    assert s["word_count"] > 20


def test_extract_signals_empty_client_rendered_page():
    s = rc.extract_signals(BAD)
    assert s["h1_count"] == 0
    assert s["has_main_content"] is False  # nothing in raw HTML — invisible to AI bots
    assert s["jsonld_types"] == []
    assert s["canonical"] is None


def test_invalid_jsonld_flagged():
    html = (
        '<html><body><script type="application/ld+json">{bad json}</script><h1>x</h1></body></html>'
    )
    s = rc.extract_signals(html)
    assert s["jsonld_valid"] is False


def test_heading_order_skip_detected():
    html = "<html><body><h1>A</h1><h4>skipped</h4></body></html>"
    s = rc.extract_signals(html)
    assert s["heading_order_ok"] is False


def test_jsonld_graph_wrapper_detected():
    # Yoast/RankMath/next-seo wrap every node inside @graph — must still be parsed.
    html = (
        "<html><body><h1>x</h1>"
        '<script type="application/ld+json">'
        '{"@context":"https://schema.org","@graph":[{"@type":"WebSite"},'
        '{"@type":"HairSalon","name":"Samir"}]}'
        "</script></body></html>"
    )
    s = rc.extract_signals(html)
    assert "HairSalon" in s["jsonld_types"]
    assert s["has_localbusiness"] is True
    assert s["jsonld_valid"] is True
