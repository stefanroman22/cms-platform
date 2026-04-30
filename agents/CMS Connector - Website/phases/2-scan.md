# Phase 2 — Scan website & generate CMS integration report

**Goal:** Produce `cms-integration-report.md` listing every recommended CMS service, grouped into sections, written for human review.

**Inputs:** `<folder_name>`, output of Phase 1, Anthropic Claude.

## Steps

1. Read source files via `file_reader.read_website_files`. Cap by size + count, skip excluded dirs.
2. Detect logo: scan `<folder_name>/public/` for `.svg`, `.png`, `.jpg`, `.jpeg`, `.webp`. Prefer filenames containing `logo`, `brand`, or `mark`. Record relative path.
3. Call Claude with `prompts.py` SYSTEM_PROMPT. **Model: `claude-opus-4-7`** — scan accuracy drives every downstream phase, so use the strongest model. Mark the system block with `cache_control: {"type": "ephemeral"}` for prompt caching on retries.
4. Compose the report (structure below).
5. Write the report to `agents/CMS Connector - Website/cms-integration-report.md`. **Temporary** — deleted at end of Phase 6.
6. Halt and ask user to review. Do not proceed until explicit approval.

## Output

`cms-integration-report.md` written to disk.

## Required report structure

```markdown
# CMS Integration Report — <project_slug>

Generated: <UTC timestamp>
Source: <folder_name>
Repo: <github_repo>

## Section 1 — General

- Display name (header / business name / person name): "<value>"  → text_block service `general_brand_name`
- Logo (if found in /public): "<relative path>" → image service `general_logo`
  - If no logo: "No logo detected in /public/. Confirm whether site uses a logo."

## Section 2 — Contact (only if contact info detected)

- Email → key_value entry `email`
- Phone → key_value entry `phone`
- Location / address → key_value entry `address`
- Schedule (opening hours) → repeater `schedule_hours` with item_schema `[day, open, close]` (only if business has hours)

## Section 3+ — Domain-specific (one per detected category)

For each:
- Section name (About / Hobbies / Projects / Experience / Menu / Services / About Us / etc.)
- Each piece of content with:
  - Suggested `service_key` (snake_case)
  - Suggested `service_type_slug`
  - Source location (`file_path:line` or component name)
  - For repeaters: full `item_schema` (key, label, type)
  - `initial_content`: extracted current values

## Section: Excluded items

List items the agent considered but rejected, with reason. Examples:
- Navigation menu links — excluded (structural)
- Button labels ("Submit", "Send", "Learn more") — excluded (UI affordance)
- Page titles in `<title>` — excluded (route metadata)
- CSS class names, Tailwind utilities — excluded
- Animation timings, breakpoints, theme tokens — excluded
- Test fixtures, mock data — excluded

## Section: Open questions for review

Anything uncertain. Examples:
- "Detected `<h1>` 'Welcome to MyShop' on Home — editable, or permanent tagline?"
- "Two image grids: gallery on About, project thumbnails on Projects. Both gallery, or Projects as repeater(title, url)?"

## Approval

User must reply "approved" before Phase 3.
```

## Hard rules (also in `prompts.py` SYSTEM_PROMPT — keep in sync)

**Always include:**
- General section every site, even if minimal.
- One service per editable string, image, or list of items the client realistically maintains.
- For services lists / menus: examine each item's structure carefully; ensure every per-item field has a corresponding repeater field. Missing a field is the most common Phase 2 bug.

**Never include:**
- Button / CTA labels
- Navigation items
- Page-level routes / page metadata
- Hard-coded UI affordance copy
- Class names, design tokens, animation config, breakpoints
- Test fixtures, mock data

**Decision rule when ambiguous:** "would a non-developer client reasonably ask 'can I change this myself?'" → include. Else exclude.

## Failure feedback

| Cause | Message |
|-------|---------|
| Source folder unreadable | "Cannot read source files in `<folder_name>`. Check permissions." |
| Claude returned non-JSON | "LLM returned malformed output. Raw response written to `agents/CMS Connector - Website/.last-llm-output.txt`." |
| Source appears binary | "Source files appear binary/corrupted. Verify the directory contains text source." |

## Self-improvement hook

When the user reviews the report and says X should have been caught (or shouldn't have been included), append to `LEARNINGS.md` under `## Phase 2 — Scan rules`. Format: `- <date>: <one-line rule>. Triggered by: <short context>.` Next run, the agent reads LEARNINGS.md and includes those rules in the SYSTEM_PROMPT for Claude.

Example learned rules:
- `- 2026-04-29: Italian/Spanish/French language toggles are configuration, not content. Triggered by: included locale strings as text_block.`
- `- 2026-05-12: For e-commerce sites, always recommend a top-level shipping_policy rich-text. Triggered by: missed shipping-policy text on three runs.`
