# agents/SEO-GEO Optimizer/tests/test_site_change_spec.py
import importlib.util
import pathlib

_p = pathlib.Path(__file__).resolve().parents[1] / "site_change_spec.py"
_spec = importlib.util.spec_from_file_location("seo_scs", _p)
scs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scs)


def test_build_minimal_blog_spec():
    s = scs.build_site_change_spec(
        project_slug="acme",
        repo="https://github.com/x/acme",
        run_id="r1",
        pages=[
            {
                "route": "/blog",
                "page_type": "blog_index",
                "consumes": "seo_articles",
                "nav": {"add": True, "label_i18n": "nav.blog"},
                "locales": ["en", "nl"],
            }
        ],
        reason="GEO articles need a /blog index",
    )
    assert s["project_slug"] == "acme" and s["branch"] == "cms-preview"
    assert s["pages"][0]["route"] == "/blog" and s["run_id"] == "r1"
    ok, errs = scs.validate_site_change_spec(s)
    assert ok and errs == []


def test_validate_rejects_bad_page_type():
    s = scs.build_site_change_spec(
        project_slug="acme",
        repo="r",
        run_id="r1",
        pages=[{"route": "/x", "page_type": "not_a_type", "locales": ["en"]}],
        reason="x",
    )
    ok, errs = scs.validate_site_change_spec(s)
    assert ok is False
    assert any("page_type" in e for e in errs)


def test_validate_requires_route_and_reason():
    s = scs.build_site_change_spec(
        project_slug="acme",
        repo="r",
        run_id="r1",
        pages=[{"page_type": "service", "locales": ["en"]}],
        reason="",
    )
    ok, errs = scs.validate_site_change_spec(s)
    assert ok is False
    assert any("route" in e for e in errs) and any("reason" in e for e in errs)


def test_cms_wiring_defaults_and_passthrough():
    s = scs.build_site_change_spec(
        project_slug="acme",
        repo="r",
        run_id="r1",
        pages=[{"route": "/blog", "page_type": "blog_index", "locales": ["en"]}],
        cms_wiring=[{"consumes": "seo_articles", "via": "GET /projects/acme/seo/public/articles"}],
        reason="x",
    )
    assert s["cms_wiring"][0]["consumes"] == "seo_articles"
    ok, _ = scs.validate_site_change_spec(s)
    assert ok
