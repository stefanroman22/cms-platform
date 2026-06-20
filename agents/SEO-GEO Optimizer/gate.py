# agents/SEO-GEO Optimizer/gate.py
"""Evaluate the visual-QA gate results. PURE: the seo-visual-qa skill drives Playwright
(render each route at each viewport per locale) + the build/link/smoke checks, then passes
the raw results here. Nothing publishes unless evaluate_gate(...)['passed'] is True.

Fail-closed: an empty/partial render set is a FAILURE, never a silent pass.
"""

from __future__ import annotations

REQUIRED_VIEWPORTS = (375, 768, 1440)  # mobile / tablet / desktop


def evaluate_gate(checks: dict) -> dict:
    failures: list[str] = []

    viewports = checks.get("viewports") or []
    seen = {v.get("width") for v in viewports}
    if not viewports:
        failures.append("No viewports rendered — cannot verify (fail-closed).")
    for w in REQUIRED_VIEWPORTS:
        if w not in seen:
            failures.append(f"Viewport {w}px not rendered.")
    for v in viewports:
        w = v.get("width", "?")
        if v.get("overflow"):
            failures.append(f"Horizontal overflow at {w}px.")
        if v.get("text_clipped"):
            failures.append(f"Text clipped/overlapping at {w}px.")
        if v.get("broken_images"):
            failures.append(f"{v['broken_images']} broken/zero-size image(s) at {w}px.")
        if v.get("tap_targets_ok") is False:
            failures.append(f"Tap targets below 44px at {w}px.")

    if checks.get("console_errors"):
        failures.append(
            f"{len(checks['console_errors'])} console error(s): {checks['console_errors'][:3]}"
        )
    if not checks.get("build_ok", False):
        failures.append("Build failed (next build did not exit 0).")
    if checks.get("broken_links"):
        failures.append(f"Broken internal link(s): {checks['broken_links'][:5]}")
    if not checks.get("smoke_ok", False):
        failures.append("playwright-user-stories smoke failed.")
    if not checks.get("content_in_raw_html", False):
        failures.append(
            "Edited content NOT present in raw server HTML (invisible to AI/Google bots)."
        )

    return {
        "passed": not failures,
        "failures": failures,
        "checked_viewports": sorted(seen - {None}),
    }
