# Example prompts — website-builder agent

Launch from `CMS - websites`, optionally with `claude --model claude-opus-4-8 --effort xhigh`.

## Minimal — let the agent decide

```
Use the website-builder agent to fetch this design and implement it in a new folder:
<Claude Design URL>
```

## Folder-name hint

```
Use the website-builder agent. Fetch <URL> and call the output folder "northwind-coffee".
```

## Explicit locales

```
Use the website-builder agent. Fetch <URL>. Locales: en (default), nl, fr. Output folder: acme-corp.
```

```
Use the website-builder agent. Fetch <URL>. English-only — single locale, no switcher.
(The agent still uses the [locale] route structure for future-proofing.)
```

## Structure hint

```
Use the website-builder agent. Build the site from <URL or local path>.
Make it 5 pages: /, /about, /services, /case-studies, /contact. Locales: en + nl.
Primary CTA points to /contact. Serif display font, sans body, restrained animations.
```

## Local folder source

```
Use the website-builder agent. The design is at C:\Users\stefa\Downloads\acme-design-export\.
Output folder: "acme-corp". Locales: en + nl + de. Read the README and implement everything.
```

## After kickoff — /goal (interactive)

See `phases/GOAL_TEMPLATE.md` for the full Preset 1/2/3 condition strings. Paste a `/goal <conditions>`
once the agent has scaffolded.

## Overnight batch — /ralph-loop

See `phases/GOAL_TEMPLATE.md`. Always set `--max-iterations`.

## Permanent rule that should stick

```
Permanent rule for all future builds: never use Inter for the body font; default to "Geist Sans".
Append to .learnings/conventions.md in this project AND to
agents/Website Builder/learnings-template/conventions.md so future builds inherit it.
```

## Inspecting what the agent did

```
Read BUILD_PLAN.md and tell me which items were checked off, then summarize the project's
.learnings/corrections.md and .learnings/conventions.md.
```

```
List every translation key in messages/en.json and show its current value in messages/nl.json.
Output as a markdown table so I can review the seed copy before connecting the CMS.
```
