# Vendored Skills

This directory holds skill content that the Solver - Issues agent injects into its prompt at runtime via `claim_issue.py._render_skills_block()`. Each `*.md` here is a verbatim copy of an upstream `SKILL.md` body; `references/` holds files those SKILL.md bodies link to.

## Why vendored, not installed at runtime?

The agent runs headless via `claude --print` on a GitHub Actions runner. There is no `Skill` tool in that environment, no plugin marketplace install step, and no interactive auth path for plugin install. Vendoring the markdown gives the agent the same methodology with zero runtime dependencies.

The prompt builder wraps each file in `<skill name='...'>` / `<reference name='...'>` XML tags and prepends a `<execution-environment>` preamble that tells the agent to apply the methodology as mindset (not by invoking `Skill` / `TodoWrite` / `Task` tools which it does not have).

## Sources

| File | Upstream | Sync date |
|------|----------|-----------|
| `karpathy-guidelines.md` | `karpathy-skills/andrej-karpathy-skills/1.0.0/skills/karpathy-guidelines/SKILL.md` | 2026-05-17 |
| `systematic-debugging.md` | `claude-plugins-official/superpowers/5.1.0/skills/systematic-debugging/SKILL.md` | 2026-05-17 |
| `writing-plans.md` | `claude-plugins-official/superpowers/5.1.0/skills/writing-plans/SKILL.md` | 2026-05-17 |
| `test-driven-development.md` | `claude-plugins-official/superpowers/5.1.0/skills/test-driven-development/SKILL.md` | 2026-05-17 |
| `verification-before-completion.md` | `claude-plugins-official/superpowers/5.1.0/skills/verification-before-completion/SKILL.md` | 2026-05-17 |
| `requesting-code-review.md` | `claude-plugins-official/superpowers/5.1.0/skills/requesting-code-review/SKILL.md` | 2026-05-17 |
| `receiving-code-review.md` | `claude-plugins-official/superpowers/5.1.0/skills/receiving-code-review/SKILL.md` | 2026-05-17 |
| `brainstorming.md` | `claude-plugins-official/superpowers/5.1.0/skills/brainstorming/SKILL.md` | 2026-05-17 |
| `references/root-cause-tracing.md` | `superpowers/5.1.0/skills/systematic-debugging/root-cause-tracing.md` | 2026-05-17 |
| `references/defense-in-depth.md` | `superpowers/5.1.0/skills/systematic-debugging/defense-in-depth.md` | 2026-05-17 |
| `references/condition-based-waiting.md` | `superpowers/5.1.0/skills/systematic-debugging/condition-based-waiting.md` | 2026-05-17 |
| `references/testing-anti-patterns.md` | `superpowers/5.1.0/skills/test-driven-development/testing-anti-patterns.md` | 2026-05-17 |
| `references/code-reviewer.md` | `superpowers/5.1.0/skills/requesting-code-review/code-reviewer.md` | 2026-05-17 |
| `references/plan-document-reviewer-prompt.md` | `superpowers/5.1.0/skills/writing-plans/plan-document-reviewer-prompt.md` | 2026-05-17 |

## How to re-sync

1. Locate the latest upstream SKILL.md in `~/.claude/plugins/cache/...`.
2. Overwrite the matching file here.
3. Diff-review for new tool references that don't exist in headless mode — if the new content tells the agent to invoke a tool it lacks (e.g. a new `Skill` invocation pattern), extend the `<execution-environment>` preamble in `claim_issue.py` to neutralize.
4. Run `pytest tests/test_claim_issue.py` — asserts every vendored skill name still appears in the rendered prompt.
5. Update the sync date column above.

## Adding a new skill

1. Add the file to `skills/`.
2. Add its stem to `VENDORED_SKILLS` in `claim_issue.py`.
3. Reference it from the appropriate Step in the protocol section of `_build_prompt`.
4. Re-run tests.
