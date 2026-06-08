"""Single source of truth for the HTML allow-list used by user-authored
fields (currently only leads.design_prompt). Run every UGC HTML string
through `sanitize_design_prompt()` before persisting it."""

import bleach

ALLOWED_TAGS = {
    "p",
    "br",
    "strong",
    "em",
    "code",
    "pre",
    "h1",
    "h2",
    "h3",
    "ul",
    "ol",
    "li",
    "a",
}

ALLOWED_ATTRS = {
    "a": ["href", "title"],
}


def sanitize_design_prompt(html: str) -> str:
    """Strip every tag/attribute outside the allow-list. Force noopener
    nofollow and target=_blank on anchors so a malicious link can't break
    the admin tab via window.opener or get reputation-weighted by Google."""
    cleaned = bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        strip=True,
    )
    cleaned = cleaned.replace("<a ", '<a rel="noopener nofollow" target="_blank" ')
    return cleaned
