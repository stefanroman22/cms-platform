"""Allow-list sanitiser for uploaded SVGs (ADR-0011). Every SVG upload is
rewritten by `sanitize_svg()` before it reaches storage: only shape elements
and presentation attributes survive, so no script, event handler,
foreignObject, external reference or DOCTYPE/entity can be stored."""

import re
import xml.etree.ElementTree as ET
from xml.parsers import expat

MAX_SVG_BYTES = 512 * 1024

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"

ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)

ALLOWED_ELEMENTS = frozenset(
    {
        "svg",
        "g",
        "path",
        "circle",
        "ellipse",
        "line",
        "polyline",
        "polygon",
        "rect",
        "defs",
        "clipPath",
        "mask",
        "linearGradient",
        "radialGradient",
        "stop",
        "use",
        "symbol",
        "title",
        "desc",
    }
)

# Un-namespaced attribute names. `xlink:href` is the only namespaced one allowed.
ALLOWED_ATTRS = frozenset(
    {
        "viewBox",
        "width",
        "height",
        "x",
        "y",
        "x1",
        "y1",
        "x2",
        "y2",
        "cx",
        "cy",
        "r",
        "rx",
        "ry",
        "d",
        "points",
        "fill",
        "stroke",
        "stroke-width",
        "stroke-linecap",
        "stroke-linejoin",
        "stroke-miterlimit",
        "stroke-dasharray",
        "stroke-dashoffset",
        "fill-rule",
        "clip-rule",
        "opacity",
        "fill-opacity",
        "stroke-opacity",
        "transform",
        "id",
        "clip-path",
        "mask",
        "offset",
        "stop-color",
        "stop-opacity",
        "gradientUnits",
        "gradientTransform",
        "preserveAspectRatio",
        "href",
        "version",
    }
)

_XLINK_HREF = f"{{{XLINK_NS}}}href"

# Value functions, each allowed only in the attributes below. Any other "("
# or ")" (image-set, var, attr, expression, calc, ...) drops the attribute.
_LOCAL_URL = re.compile(r"(?<![\w-])url\(\s*#[^()\s'\"]+\s*\)", re.IGNORECASE)
_COLOUR_FN = re.compile(r"(?<![\w-])(?:rgba?|hsla?)\([0-9.,%/\s+-]*\)", re.IGNORECASE)
_TRANSFORM_FN = re.compile(
    r"(?<![\w-])(?:matrix|translate|scale|rotate|skewX|skewY)\([0-9eE.,\s+-]*\)"
)
_URL_ATTRS = frozenset({"fill", "stroke"})
_COLOUR_ATTRS = frozenset({"fill", "stroke", "stop-color"})
_TRANSFORM_ATTRS = frozenset({"transform", "gradientTransform"})
# `mask` and `clip-path` take only "none" or exactly one local url().
_SINGLE_REF_ATTRS = frozenset({"mask", "clip-path"})
_SINGLE_REF = re.compile(r"\s*(?:none|url\(\s*#[^()\s'\"]+\s*\))\s*", re.IGNORECASE)

# Parsed-tree limits; deeper trees would overflow the recursive clean/serialise.
MAX_SVG_DEPTH = 100
MAX_SVG_ELEMENTS = 10_000


class SvgRejected(ValueError):
    """The upload is not a safe, well-formed SVG document."""


def _split(name: str) -> tuple[str | None, str]:
    """`{ns}local` -> (ns, local); `local` -> (None, local)."""
    if name.startswith("{"):
        ns, _, local = name[1:].partition("}")
        return ns, local
    return None, name


def _element_allowed(tag) -> bool:
    if not isinstance(tag, str):
        return False
    ns, local = _split(tag)
    return ns in (None, SVG_NS) and local in ALLOWED_ELEMENTS


def _value_allowed(name: str, value: str) -> bool:
    # A backslash can hide anything behind a CSS escape (u\72l, d\61ta:).
    if "\\" in value:
        return False
    lowered = value.lower()
    if "javascript:" in lowered or "data:" in lowered:
        return False
    if name in ("href", _XLINK_HREF):
        return value.startswith("#")
    if name in _SINGLE_REF_ATTRS:
        return _SINGLE_REF.fullmatch(value) is not None
    rest = value
    if name in _URL_ATTRS:
        rest = _LOCAL_URL.sub("", rest)
    if name in _COLOUR_ATTRS:
        rest = _COLOUR_FN.sub("", rest)
    if name in _TRANSFORM_ATTRS:
        rest = _TRANSFORM_FN.sub("", rest)
    return "(" not in rest and ")" not in rest


def _check_size(root: ET.Element) -> None:
    """Iteratively bound depth and element count before any recursive pass."""
    count = 0
    stack = [(root, 0)]
    while stack:
        el, depth = stack.pop()
        count += 1
        if depth > MAX_SVG_DEPTH:
            raise SvgRejected(f"elements are nested deeper than {MAX_SVG_DEPTH}")
        if count > MAX_SVG_ELEMENTS:
            raise SvgRejected(f"more than {MAX_SVG_ELEMENTS} elements")
        stack.extend((child, depth + 1) for child in el)


def _clean(el: ET.Element) -> None:
    # Namespace every element so the output root always carries the SVG xmlns.
    el.tag = f"{{{SVG_NS}}}{_split(el.tag)[1]}"
    for name, value in list(el.attrib.items()):
        keep = (name == _XLINK_HREF or name in ALLOWED_ATTRS) and _value_allowed(name, value)
        if not keep:
            del el.attrib[name]
    for child in list(el):
        if _element_allowed(child.tag):
            _clean(child)
        else:
            el.remove(child)


# UTF-32 first: its LE BOM starts with the UTF-16 LE one.
_WIDE_BOMS = (b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff", b"\xff\xfe", b"\xfe\xff")


def _reject_declaration(*_args) -> None:
    raise SvgRejected("DOCTYPE and ENTITY declarations are not allowed")


def _reject_doctype(data: bytes) -> None:
    """Parse once with expat and reject any DOCTYPE or entity declaration,
    whatever encoding expat detects. The handler fires before any expansion."""
    parser = expat.ParserCreate()
    parser.StartDoctypeDeclHandler = _reject_declaration
    parser.EntityDeclHandler = _reject_declaration
    try:
        parser.Parse(data, True)
    except expat.ExpatError as exc:
        raise SvgRejected("file is not well-formed XML") from exc


def sanitize_svg(data: bytes) -> bytes:
    """Return a rewritten, allow-listed copy of `data` as UTF-8 SVG bytes.
    Raises `SvgRejected` when the input cannot be made safe."""
    if len(data) > MAX_SVG_BYTES:
        raise SvgRejected("file exceeds the 512 KB limit")
    # NUL bytes decode as UTF-8 but mean UTF-16/32, which hides "<!DOCTYPE" below.
    if b"\x00" in data:
        raise SvgRejected("file is not UTF-8")
    if data.startswith(_WIDE_BOMS):
        raise SvgRejected("file is not UTF-8")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SvgRejected("file is not UTF-8") from exc
    lowered = text.lower()
    if "<!doctype" in lowered or "<!entity" in lowered:
        raise SvgRejected("DOCTYPE and ENTITY declarations are not allowed")
    _reject_doctype(data)
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise SvgRejected("file is not well-formed XML") from exc
    ns, local = _split(root.tag)
    if local != "svg" or ns not in (None, SVG_NS):
        raise SvgRejected("root element is not <svg>")
    _check_size(root)
    _clean(root)
    return ET.tostring(root, encoding="unicode").encode("utf-8")
