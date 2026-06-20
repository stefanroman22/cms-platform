# agents/SEO-GEO Optimizer/tests/test_gate.py
import importlib.util
import pathlib

_p = pathlib.Path(__file__).resolve().parents[1] / "gate.py"
_spec = importlib.util.spec_from_file_location("seo_gate", _p)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


def _clean_viewport(w):
    return {
        "width": w,
        "overflow": False,
        "text_clipped": False,
        "broken_images": 0,
        "tap_targets_ok": True,
    }


def test_all_green_passes():
    checks = {
        "viewports": [_clean_viewport(375), _clean_viewport(768), _clean_viewport(1440)],
        "console_errors": [],
        "build_ok": True,
        "broken_links": [],
        "smoke_ok": True,
        "content_in_raw_html": True,
    }
    r = gate.evaluate_gate(checks)
    assert r["passed"] is True
    assert r["failures"] == []


def test_overflow_fails_and_names_viewport():
    vp = [_clean_viewport(375), _clean_viewport(768), _clean_viewport(1440)]
    vp[0]["overflow"] = True
    checks = {
        "viewports": vp,
        "console_errors": [],
        "build_ok": True,
        "broken_links": [],
        "smoke_ok": True,
        "content_in_raw_html": True,
    }
    r = gate.evaluate_gate(checks)
    assert r["passed"] is False
    assert any("375" in f and "overflow" in f.lower() for f in r["failures"])


def test_console_errors_and_broken_build_fail():
    checks = {
        "viewports": [_clean_viewport(375)],
        "console_errors": ["TypeError x"],
        "build_ok": False,
        "broken_links": ["/gone"],
        "smoke_ok": False,
        "content_in_raw_html": False,
    }
    r = gate.evaluate_gate(checks)
    assert r["passed"] is False
    kinds = " ".join(r["failures"]).lower()
    for must in ["console", "build", "link", "smoke", "raw server html"]:
        assert must in kinds


def test_missing_viewports_is_a_failure_not_a_pass():
    # never green-light on an empty/partial render set
    r = gate.evaluate_gate(
        {
            "viewports": [],
            "console_errors": [],
            "build_ok": True,
            "broken_links": [],
            "smoke_ok": True,
            "content_in_raw_html": True,
        }
    )
    assert r["passed"] is False
    assert any("viewport" in f.lower() for f in r["failures"])
