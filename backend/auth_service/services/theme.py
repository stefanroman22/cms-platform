"""Project theme validation (ADR-0011).

A `theme` service holds a project's fonts, brand colours and surfaces. Every
save runs `normalize_theme`, which rebuilds the theme from known keys only and
raises `ThemeError` (→ HTTP 422) on anything the client kit could not render
safely. The family charset and URL rules mirror client-kit/rich-text/src/theme.ts."""

from __future__ import annotations

import re

MAX_COLORS = 24
MAX_SURFACES = 8
MAX_FONTS = 12
MAX_WEIGHTS = 9
MAX_FONT_FILES = 8
MAX_COLOR_NAME_LENGTH = 40

# Same pattern as the kit's FONT_FAMILY_RE (used with fullmatch).
FONT_FAMILY_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 \-]{0,63}")
_HEX_RE = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})")
# The kit drops a font URL containing any of these (it is written into CSS url("...")).
_UNSAFE_URL_RE = re.compile(r"[\"'()\\\s]")
# A "." or ".." path segment (also percent-encoded) would let a URL leave the project folder.
_DOT_SEGMENT_RE = re.compile(r"(?:^|/)(?:\.|%2e){1,2}(?:/|$)", re.I)
_FONT_STYLES = ("normal", "italic")


class ThemeError(ValueError):
    """Invalid theme content (→ HTTP 422). The message starts with the field path."""


def normalize_hex(value: object) -> str | None:
    """`#abc` / `#AABBCC` → `#aabbcc`; None when `value` is not a hex colour."""
    if not isinstance(value, str):
        return None
    m = _HEX_RE.fullmatch(value)
    if not m:
        return None
    h = m.group(1).lower()
    return "#" + ("".join(c * 2 for c in h) if len(h) == 3 else h)


def _list(raw: object, path: str, cap: int) -> list:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ThemeError(f"{path}: must be a list")
    if len(raw) > cap:
        raise ThemeError(f"{path}: at most {cap} allowed")
    return raw


def _colors(raw: object, path: str, cap: int) -> list[dict]:
    out = []
    for i, c in enumerate(_list(raw, path, cap)):
        here = f"{path}[{i}]"
        if not isinstance(c, dict):
            raise ThemeError(f"{here}: must be an object")
        name = c.get("name")
        name = name.strip() if isinstance(name, str) else ""
        if not 1 <= len(name) <= MAX_COLOR_NAME_LENGTH:
            raise ThemeError(f"{here}.name: must be 1 to {MAX_COLOR_NAME_LENGTH} characters")
        value = normalize_hex(c.get("value"))
        if value is None:
            raise ThemeError(f"{here}.value: must be a hex colour")
        out.append({"name": name, "value": value})
    return out


def _weight(value: object, path: str) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not 100 <= value <= 900
        or value % 100
    ):
        raise ThemeError(f"{path}: must be 100 to 900 in steps of 100")
    return value


def _font_url(value: object, path: str, storage_prefix: str) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith(storage_prefix)
        or _UNSAFE_URL_RE.search(value)
        or _DOT_SEGMENT_RE.search(value[len(storage_prefix) :])
    ):
        raise ThemeError(f"{path}: must be a font uploaded to this project")
    return value


def _font(f: object, path: str, storage_prefix: str) -> dict:
    if not isinstance(f, dict):
        raise ThemeError(f"{path}: must be an object")
    family = f.get("family")
    if not isinstance(family, str) or not FONT_FAMILY_RE.fullmatch(family):
        raise ThemeError(
            f"{path}.family: letters, digits, spaces and hyphens only (max 64 characters)"
        )
    source = f.get("source")
    if source == "system":
        return {"family": family, "source": "system"}
    if source == "google":
        weights = _list(f.get("weights"), f"{path}.weights", MAX_WEIGHTS)
        weights = [_weight(w, f"{path}.weights[{j}]") for j, w in enumerate(weights)]
        italic = f.get("italic", False)
        if not isinstance(italic, bool):
            raise ThemeError(f"{path}.italic: must be true or false")
        return {
            "family": family,
            "source": "google",
            "weights": sorted(set(weights)),
            "italic": italic,
        }
    if source == "upload":
        files = _list(f.get("files"), f"{path}.files", MAX_FONT_FILES)
        if not files:
            raise ThemeError(f"{path}.files: at least one font file is required")
        out_files = []
        for j, x in enumerate(files):
            here = f"{path}.files[{j}]"
            if not isinstance(x, dict):
                raise ThemeError(f"{here}: must be an object")
            style = x.get("style")
            if style not in _FONT_STYLES:
                raise ThemeError(f"{here}.style: must be normal or italic")
            out_files.append(
                {
                    "url": _font_url(x.get("url"), f"{here}.url", storage_prefix),
                    "weight": _weight(x.get("weight"), f"{here}.weight"),
                    "style": style,
                }
            )
        return {"family": family, "source": "upload", "files": out_files}
    raise ThemeError(f"{path}.source: must be google, upload or system")


def _font_ref(value: object, path: str, families: dict[str, str]) -> str:
    if value is None or value == "":
        return ""
    if not isinstance(value, str) or value.lower() not in families:
        raise ThemeError(f"{path}: must be one of the theme's fonts")
    return families[value.lower()]


def normalize_theme(content: dict, *, storage_prefix: str) -> dict:
    """Validated theme with exactly the keys colors, surfaces, fonts, body_font,
    heading_font. Uploaded font URLs must start with `storage_prefix` (the
    project's public storage folder)."""
    if not isinstance(content, dict):
        raise ThemeError("theme: must be an object")
    fonts = []
    families: dict[str, str] = {}
    for i, f in enumerate(_list(content.get("fonts"), "fonts", MAX_FONTS)):
        font = _font(f, f"fonts[{i}]", storage_prefix)
        key = font["family"].lower()
        if key in families:
            raise ThemeError(f"fonts[{i}].family: duplicate font family")
        families[key] = font["family"]
        fonts.append(font)
    return {
        "colors": _colors(content.get("colors"), "colors", MAX_COLORS),
        "surfaces": _colors(content.get("surfaces"), "surfaces", MAX_SURFACES),
        "fonts": fonts,
        "body_font": _font_ref(content.get("body_font"), "body_font", families),
        "heading_font": _font_ref(content.get("heading_font"), "heading_font", families),
    }
