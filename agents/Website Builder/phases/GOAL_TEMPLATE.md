# Completion-loop templates: `/goal` and `/ralph-loop`

Two ways to keep the agent running until the build is done. Pick one per session. Don't combine them — they fight each other.

## When to use which

| Situation | Use |
|---|---|
| Interactive build, multi-faceted completion criteria (build + tests + grep + a11y) | `/goal` |
| Overnight batch, "build N sites in a row" | `/ralph-loop` |
| First time using either | `/goal` Preset 1 |
| You want the cheapest verification loop | `/goal` (eval is fast Haiku) |
| You want a single, dead-simple completion signal | `/ralph-loop` |
| You're already in a long Claude Code session with subagents | `/goal` (sticks within the session) |

Both are documented below. The presets in `/goal` section translate cleanly to `/ralph-loop` — just take the conditions and put them in the prompt with a single promise string at the end.

---

## `/goal` — multi-condition verification

**Prerequisite:** Claude Code v2.1.139+. `claude --version` to check. Upgrade: `npm install -g @anthropic-ai/claude-code@latest`.

After the website-builder agent has scaffolded the project and started building, issue:

```
/goal <paste a condition string below>
```

After each turn, a fast Haiku evaluator checks whether the condition holds. If it does, the goal clears. If not, the agent runs another turn.

### Preset 1 — Default (recommended for first builds)

```
The site build is complete when ALL of the following are true:
1. BUILD_PLAN.md exists in the project root and every checkbox is checked.
2. `npm run build` exits with code 0 (no TypeScript or build errors).
3. `npx playwright test` exits with code 0 (all E2E specs pass).
4. The site has app/sitemap.ts, app/robots.ts, and a JSON-LD block on at least the home page.
5. A grep for "framer-motion" in app/ components/ lib/ returns zero matches.
6. A grep for "next-i18next" or "react-i18next" returns zero matches.
7. A grep for raw "<img " tags outside app/opengraph-image.tsx and app/og/ returns zero matches.
8. .learnings/conventions.md has at least one entry timestamped today.
9. No page produces horizontal overflow at 375px width (verified by the responsive Playwright test).
10. The site has app/[locale]/ as the routing structure (locale prefix in URLs).
11. messages/<locale>.json seed files exist for every configured locale and contain no `[XX]`/`[NL]` placeholder strings.
12. The locale switcher Playwright test passes.
```

### Preset 2 — Strict (block on quality)

Use only when you can afford long runs (potentially hours):

```
The site build is complete when ALL of the following are true:
1. BUILD_PLAN.md exists and every checkbox is checked.
2. `npm run build` exits with code 0.
3. `npx playwright test` exits with code 0.
4. The site has app/sitemap.ts (with hreflang alternates), app/robots.ts, and JSON-LD on the home page.
5. Grep for "framer-motion", "next-i18next", and "react-i18next" each return zero matches.
6. Grep for raw "<img " tags outside app/opengraph-image.tsx returns zero matches.
7. .learnings/conventions.md has at least one entry from today.
8. No page produces horizontal overflow at 375px width.
9. Running Lighthouse via `npx unlighthouse-ci --site http://127.0.0.1:3000` shows:
   - Performance ≥ 90 (mobile)
   - SEO ≥ 95
   - Accessibility ≥ 95
   - Best Practices ≥ 90
   on every locale × every page that exists in the sitemap.
10. `npx @axe-core/cli http://127.0.0.1:3000/en` and same for every other locale report zero violations.
11. Every page has a unique <title> and meta description per locale (no duplicates within a locale).
12. Every <Image> usage in components has alt text and a sizes prop.
13. Every visible UI string flows through next-intl translations (no hardcoded copy in components).
```

### Preset 3 — Lenient (fast iteration / prototyping)

For early-stage exploration when you want a quick visual:

```
The site build is complete when:
1. BUILD_PLAN.md has every checkbox checked.
2. `npm run build` exits with code 0.
3. The home page renders at http://127.0.0.1:3000/en without console errors.
4. At least one Playwright test passes.
```

---

## `/ralph-loop` — autonomous bash-loop-style

**Prerequisite:** Ralph Wiggum plugin installed. See INSTALL.md for the install command.

The plugin intercepts Claude's exit attempts and re-feeds the same prompt until the agent emits the promise string. Best for overnight runs.

### Basic invocation

```
/ralph-loop "Use the website-builder agent. Fetch <design-url>, read its README,
and implement the design in a new sibling folder under
C:\Users\stefa\.gemini\antigravity\scratch\.

Locales: en, nl.

Verification checklist (do not emit the completion promise until all are true):
1. BUILD_PLAN.md every checkbox checked
2. npm run build exits 0
3. npx playwright test exits 0
4. No 'framer-motion', 'next-i18next', 'react-i18next' in the codebase
5. No raw <img tags outside opengraph-image.tsx
6. Sitemap includes every locale x every path

After 15 iterations, if not complete, document blocker in .learnings/failure-modes.md
and ask the user.

Output <promise>SITE_COMPLETE</promise> only when ALL conditions are verified."
--completion-promise "SITE_COMPLETE"
--max-iterations 25
```

### Batch invocation — multiple sites overnight

```powershell
cat <<'EOF' > overnight.ps1
cd "C:\Users\stefa\.gemini\antigravity\scratch\CMS - websites"

claude -p "/ralph-loop 'Use the website-builder agent to build the site at <url-1> with locales en+nl. Output <promise>SITE_1_DONE</promise> when verified.' --completion-promise 'SITE_1_DONE' --max-iterations 30"

claude -p "/ralph-loop 'Use the website-builder agent to build the site at <url-2> with locales en+nl+fr. Output <promise>SITE_2_DONE</promise> when verified.' --completion-promise 'SITE_2_DONE' --max-iterations 30"
EOF

./overnight.ps1
```

Each session is independent. Costs: figure roughly $5–15 per site for a typical 3–5 page build. A 50-iteration runaway can hit $50+ — always set `--max-iterations`.

### When `/ralph-loop` is the wrong tool

- The completion condition has many parts you want individually verified (use `/goal` — its multi-condition syntax is more honest about what's actually done).
- You need to inspect intermediate progress (Ralph hides intermediate turns by design).
- You're paying-per-token without a Pro/Max subscription — autonomous loops burn tokens fast.

---

## Common gotchas (both modes)

- **Loop on the same error.** The agent prompt instructs it to escalate after 3 retries on the same item — but if you see the same diff repeatedly, manually interrupt with Ctrl-C and inspect `.learnings/failure-modes.md`.
- **Playwright can't start the dev server.** If the test step hangs, check port 3000 isn't already in use, and that Windows Defender isn't blocking Node. The `webServer.timeout: 120_000` in `playwright.config.ts` gives 2 minutes for first start.
- **`/goal` does not pause for clarifying questions.** If the agent needs to ask you something, it will end its turn with a question. The evaluator sees the condition isn't met, the agent gets called again, and it'll keep asking until you respond. Check periodically.
- **`/ralph-loop` does not pause for clarifying questions either.** Same deal — if the agent asks something, the loop will re-prompt the SAME original prompt. The agent's prompt instructs it to escalate to the user after 3 retries; honor that contract.

## Picking the right preset

| Situation | Use |
|---|---|
| First time building a site for a client | `/goal` Preset 1 |
| Building a final deliverable for a real launch | `/goal` Preset 2 |
| Trying out a new design quickly to see how it looks | `/goal` Preset 3 |
| Refining an existing site to fix specific issues | Custom — write a condition naming the specific files/checks |
| Overnight build of 2+ sites in sequence | `/ralph-loop` with conditions from Preset 1 |
