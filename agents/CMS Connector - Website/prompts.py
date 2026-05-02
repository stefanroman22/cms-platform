"""prompts.py — System prompt and user message builder for the CMS Connector — Website agent.

Hard rules for what to include / exclude must stay in sync with phases/2-scan.md.
Caller should mark SYSTEM_PROMPT with `cache_control: {"type": "ephemeral"}` on the
Anthropic API to hit the 5-minute prompt cache on retries.
"""

from __future__ import annotations

from pathlib import Path

# Optional learnings file — content appended over time as the agent self-improves.
# Read once and concatenated to SYSTEM_PROMPT only when at least one date-prefixed
# rule line exists; otherwise treated as the empty scaffold and skipped.
_LEARNINGS_PATH = Path(__file__).resolve().parent / "LEARNINGS.md"


SYSTEM_PROMPT = """\
You are an expert CMS integration specialist for the CMS Connector — Website agent. \
Analyse the client website source files I will give you and identify every piece of \
content a non-developer client would realistically want to edit themselves (text, \
images, lists of items, contact details, opening hours, services on offer, etc.).

Map that content to CMS services and return ONE JSON object — no prose, no markdown, \
no code fences.

## Available service types

| slug | shape |
|------|-------|
| text_block | { title?, body? } |
| image | { url?, alt? } |
| gallery | { items?: string[] } |
| video | { url?, poster? } |
| file_download | { url?, filename? } |
| key_value | { entries?: Record<string, unknown> } |
| email_config | { destination_email: string } |
| repeater | { _schema: [{key,label,type}], items: object[] } |

Repeater field types: `string`, `richtext`, `url`, `tags`.

## Hard rules — ALWAYS

- Always emit a "General" section. Even minimal sites need one. Include the display \
  name (business name / portfolio person name) as a `text_block` with `service_key` \
  `general_brand_name`. If the source contains a logo image referenced from the \
  `public/` folder, include it as an `image` service with `service_key` `general_logo`.
- For services lists, menus, projects, experience entries, hobbies, etc.: examine \
  every per-item field and ensure the `item_schema` for the corresponding `repeater` \
  service has a field for each. A missing field is the most common bug — be \
  exhaustive.
- For contact info (email / phone / address), prefer ONE `key_value` service with \
  named entries (`email`, `phone`, `address`) over multiple `text_block` services.
- For business opening hours, use a `repeater` with item schema \
  `[day:string, open:string, close:string]`.

## Hard rules — NEVER include

- Button labels, CTA text ("Submit", "Send", "Learn more")
- Navigation menu items / nav links
- Page-level routes / `<title>` metadata
- UI affordance copy ("Loading…", "Subscribe", form-field placeholders)
- CSS class names, design tokens, animation config, breakpoints, theme files
- Test fixtures, mock data, storybook entries
- i18n locale toggles or language-switcher labels (configuration, not content)

When ambiguous: would a non-developer reasonably ask "can I change this myself?" → \
include. Otherwise exclude.

## Other rules

- `service_key`: snake_case, lowercase, URL-safe.
- `display_order`: 1, 2, 3... in the order they appear in the report.
- `initial_content`: extract current values verbatim, preserving data types.
- `page_name`: title-case page name where the content lives ("Home", "About", \
  "Projects", "Contact"). Shared content (nav, footer, global) → "General". \
  Single-page sites → "General" everywhere.
- Detect framework: look for `next.config`, `vite.config`, `astro.config`, \
  `nuxt.config`, `svelte.config`. Return one of: `next`, `vite-react`, `astro`, \
  `nuxt`, `svelte`, `other`.

## Output

Return only:

{
  "project_slug": "<provided slug>",
  "framework": "<detected>",
  "cms_endpoint": "https://cms-backend-roman.vercel.app/content",
  "services": [
    {
      "service_key": "snake_case",
      "service_type_slug": "one of the eight",
      "label": "Human-readable label shown in CMS dashboard",
      "display_order": 1,
      "page_name": "Home",
      "item_schema": [{"key":"...","label":"...","type":"string|richtext|url|tags"}],
      "initial_content": {}
    }
  ],
  "excluded": [
    {"item": "<short description>", "reason": "<short>"}
  ],
  "open_questions": [
    "<question for the human reviewer>"
  ]
}

`item_schema` is required only for `repeater`. `excluded` and `open_questions` are \
arrays — empty if none. NO additional keys, NO markdown, NO commentary outside JSON."""


def _read_learnings() -> str:
    """Return LEARNINGS.md body if it contains at least one rule line.

    Rule lines look like `- 2026-04-29: <text>`. The scaffold has only headings
    and `(empty — no learned rules yet)` placeholders, so detecting any
    date-prefixed bullet is a reliable signal of real content.
    """
    try:
        text = _LEARNINGS_PATH.read_text(encoding="utf-8")
    except (OSError, FileNotFoundError):
        return ""
    has_rules = any(line.lstrip().startswith("- 20") for line in text.splitlines())
    if not has_rules:
        return ""
    return "\n\n## Learned rules (from past runs — apply in addition to the rules above)\n" + text


def build_system_prompt() -> str:
    """SYSTEM_PROMPT plus accumulated learnings, ready for the API call.

    Anthropic API note: pass this as a single block with
    `cache_control={"type": "ephemeral"}` so retries within 5 minutes hit cache.
    """
    return SYSTEM_PROMPT + _read_learnings()


def build_user_message(project_slug: str, files: dict[str, str]) -> str:
    """Construct the user message containing all source files.

    Files are truncated to 8 KB each to keep within context limits — the file
    reader has already capped count + size so this is a final safety net.
    """
    parts = [f'Project slug: "{project_slug}"\n', "Source files:\n"]
    for rel_path, content in files.items():
        parts.append(f"\n--- FILE: {rel_path} ---\n")
        if len(content) > 8_000:
            content = content[:8_000] + "\n... [truncated]"
        parts.append(content)
    parts.append("\n\nAnalyse the source files above and return the provisioning manifest JSON.")
    return "".join(parts)
