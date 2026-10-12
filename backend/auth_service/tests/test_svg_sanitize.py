"""Tests for the allow-list SVG sanitiser (ADR-0011)."""

import pytest

from auth_service.services.svg_sanitize import MAX_SVG_BYTES, SvgRejected, sanitize_svg

SVG_NS = 'xmlns="http://www.w3.org/2000/svg"'
XLINK_NS = 'xmlns:xlink="http://www.w3.org/1999/xlink"'


def _clean(svg: str) -> str:
    return sanitize_svg(svg.encode("utf-8")).decode("utf-8")


def test_keeps_lucide_style_icon():
    out = _clean(
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M1 1h2"/></svg>'
    )
    assert out.startswith("<svg ")
    assert SVG_NS in out
    assert 'viewBox="0 0 24 24"' in out
    assert 'fill="none"' in out
    assert 'stroke="currentColor"' in out
    assert '<path d="M1 1h2" />' in out


def test_namespaced_input_keeps_default_namespace():
    out = _clean(f'<svg {SVG_NS} viewBox="0 0 8 8"><circle cx="4" cy="4" r="2"/></svg>')
    assert "ns0:" not in out
    assert SVG_NS in out
    assert '<circle cx="4" cy="4" r="2" />' in out


def test_strips_script():
    out = _clean(f'<svg {SVG_NS}><script>alert(1)</script><path d="M0 0"/></svg>')
    assert "script" not in out
    assert "alert" not in out
    assert '<path d="M0 0" />' in out


def test_strips_event_handler():
    out = _clean(f'<svg {SVG_NS} onload="alert(1)"><rect onclick="x()" width="1"/></svg>')
    assert "onload" not in out
    assert "onclick" not in out
    assert "alert" not in out
    assert 'width="1"' in out


def test_strips_foreign_object_with_subtree():
    out = _clean(
        f"<svg {SVG_NS}><foreignObject><div>hi</div><path d='M0 0'/></foreignObject></svg>"
    )
    assert "foreignObject" not in out
    assert "div" not in out
    assert "path" not in out


def test_strips_image_element():
    out = _clean(f'<svg {SVG_NS}><image href="http://x"/><g/></svg>')
    assert "image" not in out
    assert "http://x" not in out
    assert "<g />" in out


def test_strips_style_and_class():
    out = _clean(f'<svg {SVG_NS}><path style="fill:red" class="a" d="M0 0"/></svg>')
    assert "style" not in out
    assert "class" not in out
    assert 'd="M0 0"' in out


def test_strips_style_element():
    out = _clean(f"<svg {SVG_NS}><style>path{{fill:url(http://evil)}}</style></svg>")
    assert "style" not in out
    assert "evil" not in out


def test_strips_javascript_xlink_href():
    out = _clean(f'<svg {SVG_NS} {XLINK_NS}><use xlink:href="javascript:alert(1)"/></svg>')
    assert "javascript" not in out
    assert "href" not in out
    assert "<use />" in out


def test_strips_external_href():
    out = _clean(f'<svg {SVG_NS}><use href="http://evil/x.svg#a"/></svg>')
    assert "evil" not in out


def test_keeps_local_href():
    out = _clean(
        f'<svg {SVG_NS} {XLINK_NS}><symbol id="s"/><use href="#s"/><use xlink:href="#s"/></svg>'
    )
    assert '<use href="#s" />' in out
    assert 'xlink:href="#s"' in out


def test_strips_external_url_fill():
    out = _clean(f'<svg {SVG_NS}><rect fill="url(http://evil)" width="1"/></svg>')
    assert "evil" not in out
    assert "fill" not in out
    assert 'width="1"' in out


def test_strips_mixed_url_values():
    out = _clean(f'<svg {SVG_NS}><rect fill="url(#g) url(http://evil)"/></svg>')
    assert "evil" not in out


def test_keeps_local_url_gradient():
    out = _clean(
        f"<svg {SVG_NS}><defs><linearGradient id='g'>"
        f"<stop offset='0' stop-color='#fff'/></linearGradient></defs>"
        f"<rect fill='url(#g)' width='1'/></svg>"
    )
    assert '<linearGradient id="g">' in out
    assert '<stop offset="0" stop-color="#fff" />' in out
    assert 'fill="url(#g)"' in out


def test_drops_data_uri_value():
    out = _clean(f'<svg {SVG_NS}><rect fill="data:text/html,x" width="1"/></svg>')
    assert "data:" not in out


@pytest.mark.parametrize(
    ("attr", "value"),
    [
        ("fill", r"u\72l(http://evil/x.svg#p)"),
        ("fill", r"u\rl(http://evil/x.svg#p)"),
        ("mask", "image-set('http://evil/x.png' 1x)"),
        ("fill", "image-set('http://evil/x.png' 1x)"),
        ("fill", r"url(d\61ta:image/png,x)"),
        ("fill", r"d\61ta:x"),
        ("fill", "var(--x)"),
        ("fill", "attr(id)"),
        ("fill", "expression(alert(1))"),
        ("fill", "u/**/rl(http://evil)"),
        ("fill", "rgb(url(http://evil))"),
        ("stroke", "url(#a)(http://evil)"),
        ("stop-color", "url(#g)"),
        ("opacity", "rgb(1,2,3)"),
        ("transform", "url(#g)"),
        ("transform", "translate(var(--x))"),
        ("d", "M0 0 (1)"),
        ("points", "0,0 1,1)"),
        ("width", "calc(1px)"),
        ("mask", "url(#a) url(#b)"),
        ("clip-path", "circle(5px)"),
        ("clip-path", "rgb(1,2,3)"),
    ],
)
def test_drops_unsafe_function_values(attr, value):
    out = _clean(f"<svg {SVG_NS}><rect {attr}=\"{value}\" x='1'/></svg>")
    assert f'{attr}="' not in out
    assert "evil" not in out
    assert 'x="1"' in out


@pytest.mark.parametrize(
    ("attr", "value"),
    [
        ("fill", "rgb(1,2,3)"),
        ("fill", "rgba(1, 2, 3, 0.5)"),
        ("stroke", "hsl(120, 50%, 50%)"),
        ("stop-color", "hsla(120 50% 50% / 0.5)"),
        ("transform", "translate(1 2) rotate(45)"),
        ("transform", "matrix(1,0,0,1,-2.5e1,3) scale(2) skewX(10) skewY(-5)"),
        ("gradientTransform", "rotate(90 0.5 0.5)"),
        ("fill", "url(#g) red"),
        ("mask", "url(#m)"),
        ("clip-path", "none"),
        ("clip-path", "url(#c)"),
        ("d", "M0 0L1 1z"),
    ],
)
def test_keeps_allowed_function_values(attr, value):
    out = _clean(f'<svg {SVG_NS}><rect {attr}="{value}"/></svg>')
    assert f'{attr}="{value}"' in out


def test_rejects_deep_nesting():
    depth = 5000
    svg = f"<svg {SVG_NS}>" + "<g>" * depth + "</g>" * depth + "</svg>"
    with pytest.raises(SvgRejected):
        sanitize_svg(svg.encode())


def test_nesting_limit_boundary():
    def nested(depth: int) -> bytes:  # root svg is depth 0
        return (f"<svg {SVG_NS}>" + "<g>" * depth + "</g>" * depth + "</svg>").encode()

    assert sanitize_svg(nested(100)).count(b"<g>") == 99  # innermost is <g />
    with pytest.raises(SvgRejected):
        sanitize_svg(nested(101))


def test_rejects_too_many_elements():
    svg = f"<svg {SVG_NS}>" + "<g/>" * 10_001 + "</svg>"
    with pytest.raises(SvgRejected):
        sanitize_svg(svg.encode())


def test_rejects_doctype_entity_bomb():
    bomb = (
        '<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">'
        '<!ENTITY lol2 "&lol;&lol;&lol;">]>'
        f"<svg {SVG_NS}><title>&lol2;</title></svg>"
    )
    with pytest.raises(SvgRejected):
        sanitize_svg(bomb.encode("utf-8"))


def test_rejects_lowercase_entity_without_doctype_keyword():
    with pytest.raises(SvgRejected):
        sanitize_svg(b'<!entity x "y"><svg/>')


_ENTITY_DOC = (
    '<!DOCTYPE svg [<!ENTITY a "boom"><!ENTITY b "&a;&a;&a;">]>'
    f"<svg {SVG_NS}><title>&b;</title></svg>"
)


@pytest.mark.parametrize("bom", [b"", b"\xff\xfe"])
def test_rejects_utf16le_doctype_with_entities(bom):
    # NUL bytes are valid UTF-8, so a UTF-16 file passes the UTF-8 decode while
    # its "<!DOCTYPE" never matches as a substring; expat still expands it.
    data = bom + ('<?xml version="1.0" encoding="UTF-16"?>' + _ENTITY_DOC).encode("utf-16-le")
    with pytest.raises(SvgRejected):
        sanitize_svg(data)


@pytest.mark.parametrize(
    "bom", [b"\xff\xfe", b"\xfe\xff", b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff"]
)
def test_rejects_utf16_and_utf32_bom(bom):
    with pytest.raises(SvgRejected):
        sanitize_svg(bom + f"<svg {SVG_NS}/>".encode())


def test_rejects_nul_byte():
    with pytest.raises(SvgRejected):
        sanitize_svg(f"<svg {SVG_NS}><title>a\x00b</title></svg>".encode())


@pytest.mark.parametrize("lead", ["  \n\t", "<!-- logo -->", '<?xml version="1.0"?>\n<!-- x -->\n'])
def test_rejects_doctype_after_whitespace_or_comment(lead):
    with pytest.raises(SvgRejected):
        sanitize_svg((lead + _ENTITY_DOC).encode())


def test_parser_guard_rejects_any_doctype():
    # The expat pass rejects a DOCTYPE on its own, independent of the substring check.
    from auth_service.services.svg_sanitize import _reject_doctype

    with pytest.raises(SvgRejected):
        _reject_doctype(_ENTITY_DOC.encode())
    with pytest.raises(SvgRejected):
        _reject_doctype(f"<!DOCTYPE svg><svg {SVG_NS}/>".encode())
    _reject_doctype(f"<svg {SVG_NS}/>".encode())


def test_rejects_non_svg_root():
    with pytest.raises(SvgRejected):
        sanitize_svg(b"<html><body/></html>")


def test_rejects_oversized_input():
    pad = "<g/>" * (MAX_SVG_BYTES // 4)
    with pytest.raises(SvgRejected):
        sanitize_svg(f"<svg {SVG_NS}>{pad}</svg>".encode())


def test_rejects_malformed_xml():
    with pytest.raises(SvgRejected):
        sanitize_svg(b"<svg><path></svg>")


def test_rejects_non_utf8():
    with pytest.raises(SvgRejected):
        sanitize_svg(b"<svg>\xff\xfe</svg>")


def test_svg_rejected_is_value_error():
    assert issubclass(SvgRejected, ValueError)
