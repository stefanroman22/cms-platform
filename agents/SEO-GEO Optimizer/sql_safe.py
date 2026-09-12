# agents/SEO-GEO Optimizer/sql_safe.py
"""Deterministic SQL-literal escaping for values that flow into
`mcp__supabase__execute_sql` (SEC-061).

The SEO-GEO agent has no parameterized DB path — every read/write is a raw SQL
string handed to `execute_sql` against the shared, RLS-bypassed project
`xeluydwpgiddbamysgyu`. Competitor/local values (competitor `name`, `url`, `city`,
scraped `headings`, the reasoned `analysis`, the `signals` JSON) originate from
scraped third-party sites and LLM prose, so they are UNTRUSTED. Interpolating
them into single-quoted SQL literals by hand is a SQL-injection path: a business
name like ``x','y'); drop table seo_competitors; --`` breaks out of the literal
and runs cross-tenant against a service-role connection.

ALWAYS wrap such values with `literal()` / `json_literal()` below before placing
them in an `execute_sql` query — never paste a raw scraped/LLM value between
quotes yourself. These are plain Python helpers (stdlib only), invoked the same
way the agent already calls `competitor.extract_competitor_signals(...)`.

Safety basis: Postgres runs with `standard_conforming_strings = on` (the default
since 9.1, and Supabase's default), so a single-quoted literal is terminated only
by an unescaped ``'`` and backslashes are literal. Doubling embedded single
quotes therefore fully neutralizes breakout; NUL (which Postgres text cannot
store) is rejected outright.

NOTE (SEC-061): this is a mitigation, not a substitute for real parameterized
queries. The durable fix is to persist `seo_*` rows through a parameterized
backend endpoint (like the existing `POST /projects/{slug}/seo/translate`) instead
of `execute_sql`, and to restrict the agent's Supabase MCP grant to a role that
cannot reach other tenants' tables. Until that lands, this primitive removes the
hand-escaping gap the finding identified ("no escaping/parameterization guidance
anywhere in the agent").
"""

from __future__ import annotations

import json
from typing import Any


class UnsafeSQLValueError(ValueError):
    """Raised when a value cannot be safely rendered as a SQL literal."""


def literal(value: Any) -> str:
    """Return a safe, single-quoted SQL string literal for ``value``.

    Doubles embedded single quotes (standard SQL escaping) and rejects a NUL
    byte. The returned string INCLUDES its surrounding quotes, so use it directly
    in a query, e.g.::

        f"INSERT INTO seo_competitors (name, url) "
        f"VALUES ({literal(name)}, {literal(url)})"

    ``None`` renders as the unquoted SQL keyword ``NULL``. Non-string scalars are
    coerced with ``str()`` first (so pass pre-formatted values for numbers/uuids
    when you want a specific representation).
    """
    if value is None:
        return "NULL"
    s = value if isinstance(value, str) else str(value)
    if "\x00" in s:
        raise UnsafeSQLValueError("NUL byte is not allowed in a SQL string literal")
    return "'" + s.replace("'", "''") + "'"


def json_literal(obj: Any) -> str:
    """Return a safe SQL literal for a JSON value, cast to ``::jsonb``.

    Serializes ``obj`` with ``json.dumps`` (JSON-escaping quotes/backslashes),
    then applies the same SQL-literal escaping as :func:`literal`, and appends the
    ``::jsonb`` cast. Use for the ``signals`` column, e.g.::

        f"... , {json_literal(signals)}, ..."   # -> '{"k": "v"}'::jsonb
    """
    return literal(json.dumps(obj, ensure_ascii=False)) + "::jsonb"
