# CMS Connector → Vite + React 19 (SSG) aware — Plan B (connector only)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make the CMS Connector agent correctly wire websites built on the new Vite + React 19 (SSG) stack, while KEEPING its existing Next.js support for legacy client sites (samir, Laurian, it-global). The SEO/GEO Optimizer agent is explicitly **frozen** this pass — the connector only updates how a Vite site **consumes** the SEO public endpoints; it never edits the SEO/GEO agent's files or `seo_*` tables.

**Architecture:** Additive, framework-aware branching. The connector already detects framework (`next` / `vite-react` / `astro` / …) and already has a `VITE_` env-prefix branch. We add a `vite-react` branch to the Next-first prose in `prompts.py`, `phases/4-integration.md`, and `AGENTS.md`, using the website-builder's ACTUAL canonical paths and the Option-B freshness model (client TanStack Query fetch + build-time SSG snapshot, no ISR). The react-i18next `t()` + `messages/<locale>.json` shape is identical to next-intl's, so the content deep-merge logic carries with only path changes.

**Tech the Vite branch targets (verbatim — from the shipped builder):**
- Env: `VITE_CMS_ENDPOINT`, `VITE_CMS_PREVIEW_TOKEN`, `VITE_BOOKING_API_BASE`.
- Content: `src/lib/cms-content.ts` (client fetch via TanStack Query, localStorage-persisted; merges CMS payload over `src/i18n/messages/<locale>.json`), `src/lib/cms-site.ts` `resolveSite(messages)`, `src/lib/site.ts` constants. Same per-service-type mapping and `t("<service_key>.<field>")` shape as next-intl.
- i18n: react-i18next; locale from `i18n.language`; `SUPPORTED_LOCALES`/`DEFAULT_LOCALE` in `src/lib/config.ts`.
- SEO consumption: `src/lib/seo-meta.ts` (build-time fetch for the SSG snapshot + client TanStack refetch; never throws), `src/lib/head.ts` (React 19 hoisted tags + coded tags local per locale) — **no `generateMetadata`, no ISR**. `/blog` + `/blog/:slug` pre-rendered from build-time article slugs + client refetch for freshness.
- Freshness (Option B): draft-vs-published by `VITE_CMS_PREVIEW_TOKEN` presence (preview deploy only) — token present → fetch `{base}/{locale}/draft` (header `X-CMS-Preview-Token`, `cache:'no-store'`, TanStack `staleTime:0`); absent → `{base}/{locale}` (published, `staleTime` minutes) + the build-time snapshot. CMS publish appears on next client load (no rebuild for humans); crawler snapshot refreshes on rebuild.

## Global Constraints
- **Additive / multi-framework:** never delete or weaken the existing `next` wiring — ADD a `vite-react` branch beside it. The connector still manages live Next client sites.
- **SEO/GEO frozen:** do NOT edit anything under `agents/SEO-GEO Optimizer/` or any `seo_*` table behavior. Only the connector's *consumption-wiring description* changes. Keep the "NEVER provision/clobber `seo_*`" hard rule intact.
- **Vite paths are verbatim** (above) — match the shipped builder, not generic guesses (NOT `public/locales/...`, NOT react-helmet).
- **Commits:** no auto-commit (standing rule) — stage/edit on disk; controller offers a commit at the end.
- These are agent instruction files (Markdown) + one tiny Python default; verification = direct-file read + Bash grep.

## File Structure (Plan B touches)
```
agents/CMS Connector - Website/scan.py                  # MODIFY  (_env_prefix default → VITE_)
agents/CMS Connector - Website/prompts.py               # MODIFY  (t() framework-agnostic note + Vite locale-detect paths)
agents/CMS Connector - Website/phases/4-integration.md  # MODIFY  (vite-react branches: content-wiring + draft fetch + SEO-area)
agents/CMS Connector - Website/AGENTS.md                # MODIFY  (vite-react branch: multilingual + SEO/GEO contracts)
agents/CMS Connector - Website/LEARNINGS.md             # MODIFY  (append Vite connector entry)
```

---

### Task 1: `scan.py` — default env prefix → VITE_

**Files:** Modify `agents/CMS Connector - Website/scan.py` (`_env_prefix`).

- [ ] **Step 1:** In `_env_prefix`, change the final fallback `return "NEXT_PUBLIC_"` to `return "VITE_"` and update the docstring/comment to note Vite is the pipeline default now; keep the explicit `next`/`vite`/`astro` branches unchanged.
- [ ] **Step 2: Verify** `grep -nE "return \"VITE_\"|return \"NEXT_PUBLIC_\"|def _env_prefix" "agents/CMS Connector - Website/scan.py"` → the explicit `next` branch still returns `NEXT_PUBLIC_`, the fallback returns `VITE_`.
- [ ] **Step 3: Sanity** that nothing else relied on the old default (the explicit branches are unchanged, so detected frameworks are unaffected; only undetected/`other` flips to VITE_).

---

### Task 2: `prompts.py` — framework-agnostic `t()` + Vite locale detection

**Files:** Modify `agents/CMS Connector - Website/prompts.py`.

- [ ] **Step 1:** At the `service_key` namespace note (~lines 85–86), add that `t("<service_key>.<field>")` is **framework-agnostic** — next-intl for Next sites, **react-i18next** for Vite sites — the namespaced-key shape is identical, so the same `service_key`s work for both.
- [ ] **Step 2:** At the locale-detection prose (~lines 94–100), add the Vite + react-i18next variant: read locales from `src/lib/config.ts` (`SUPPORTED_LOCALES`/`DEFAULT_LOCALE`) and/or `src/i18n/config.ts`, with seed messages at `src/i18n/messages/<locale>.json` (NOT `public/locales/...`). Keep the existing Next/next-intl detection (`i18n/routing.ts`, `messages/<locale>.json`).
- [ ] **Step 3:** Leave the framework-detection list (already returns `vite-react`) and booking/output sections unchanged.
- [ ] **Step 4: Verify** `grep -nE "react-i18next|src/i18n/messages|SUPPORTED_LOCALES|framework-agnostic" "agents/CMS Connector - Website/prompts.py"` → present; `grep -nE "vite-react" ...` still present.

---

### Task 3: `phases/4-integration.md` — add `vite-react` wiring branches

**Files:** Modify `agents/CMS Connector - Website/phases/4-integration.md`.

- [ ] **Step 1 — Content wiring (the `lib/cms-content.ts` / `lib/cms-site.ts` / `lib/site.ts` block):** add a clearly-labelled **Vite + React 19 SPA** branch beside the Next one:
  - Files live under `src/lib/` (`src/lib/cms-content.ts`, `src/lib/cms-site.ts`, `src/lib/site.ts`).
  - `src/lib/cms-content.ts` fetches CLIENT-SIDE via **TanStack Query** (localStorage-persisted) and **deep-merges the CMS payload over `src/i18n/messages/<locale>.json`** — SAME per-service-type mapping (`text_block`→key, `key_value`→namespace `entries`, `repeater`→items, `image`/`gallery`→`site.*`) and the dedicated `site` namespace. The merge logic is identical; only the path + fetch mechanism differ.
  - `src/lib/cms-site.ts` `resolveSite(messages)` is unchanged in contract; reads merged messages via the react-i18next context/`useTranslation` instead of `getMessages()`.
  - A build-time snapshot of published content is baked by SSG; the client refetch keeps humans fresh.
- [ ] **Step 2 — Draft vs published fetch:** add the Vite branch: branch on `VITE_CMS_PREVIEW_TOKEN` (present only on preview deploys + localhost `.env.local`). Present → fetch `{base}/{locale}/draft` with `X-CMS-Preview-Token` header, `cache:'no-store'`, TanStack `staleTime:0`. Absent → fetch `{base}/{locale}` (published) with a short `staleTime`. **No `next:{revalidate}` / ISR** — CMS edits appear on the next client load; the crawler snapshot refreshes on rebuild. Keep the Next ISR branch as-is for legacy sites.
- [ ] **Step 3 — SEO-area wiring (4.1.7):** add the Vite branch:
  - `src/lib/seo-meta.ts` fetches `GET {backend}/projects/{slug}/seo/public/meta?route=&locale=<locale>` at **build time** (snapshot) + optional client TanStack refetch; prefers stored prose, falls back to build-time `seo-pro` output, **never throws**. (Replaces the `next:{revalidate:60}` ISR helper.)
  - **No `generateMetadata`** — `src/lib/head.ts` emits React 19 hoisted `<title>/<meta>/<link>`; coded tags (`canonical`, `hreflang`, `og:locale`, JSON-LD `inLanguage`) generated **locally per locale**. Per-field default-locale fallback applied by the endpoint (site never merges locales).
  - `/blog` + `/blog/:slug` are **pre-rendered from build-time article slugs** (`GET …/seo/public/articles?locale=<locale>`) + client refetch for freshness; set `projects.seo_blog_route` exactly as today, only once the SEO agent has created articles.
  - Keep the existing Next `generateMetadata`/ISR branch for legacy sites; keep the **"NEVER provision/clobber `seo_*`"** hard rule.
- [ ] **Step 4 — Env prefix:** confirm the CMS-endpoint env-prefix block already lists `VITE_` (it does); add `VITE_CMS_PREVIEW_TOKEN` alongside.
- [ ] **Step 5: Verify** `grep -nE "vite|VITE_CMS|src/lib/cms-content|src/lib/head|src/lib/seo-meta|TanStack|react-i18next|/blog/:slug" "agents/CMS Connector - Website/phases/4-integration.md"` → present; `grep -nE "generateMetadata|next:\{ ?revalidate|active.?locale" ...` → only inside the explicit **Next** legacy branch, never as the sole/only instruction.

---

### Task 4: `AGENTS.md` — framework-aware contracts

**Files:** Modify `agents/CMS Connector - Website/AGENTS.md`.

- [ ] **Step 1 — Multilingual fetch contract (~148–155):** add a Vite branch — for react-i18next sites the active locale comes from `i18n.language` (and the URL `/:locale` segment), not the next-intl context; the per-locale `GET {base}/content/{slug}/{locale}` fetch + flat `Record<string,string>` contract is otherwise UNCHANGED. Keep the Next/next-intl wording for legacy sites.
- [ ] **Step 2 — SEO/GEO area contract (~156–186):** add a Vite branch — Vite SPA has **no `generateMetadata`**; it (a) bakes stored SEO into the SSG snapshot at build time, (b) refetches `seo/public/meta` + `seo/public/articles` client-side (TanStack) for freshness/preview, (c) generates coded tags locally per locale in `src/lib/head.ts`. Same read endpoints, no ISR. Keep the Next branch + the **"NEVER provision/clobber `seo_*`"** hard rule verbatim.
- [ ] **Step 3: Verify** `grep -nE "i18n\.language|react-i18next|src/lib/head|SSG snapshot|TanStack|build time" "agents/CMS Connector - Website/AGENTS.md"` → present; the "NEVER provision …`seo_*`" rule still present; no SEO/GEO-agent file referenced for EDITING.

---

### Task 5: `LEARNINGS.md` — append the Vite connector entry

**Files:** Modify `agents/CMS Connector - Website/LEARNINGS.md` (append only).

- [ ] **Step 1:** Append a dated entry (2026-06-21): the website-builder now ships Vite + React 19 (SSG) sites; the connector wires them framework-aware — `VITE_*` env, `src/lib/cms-content.ts` client TanStack fetch + build snapshot (no ISR), react-i18next `t()`/`messages/<locale>.json` shape identical to next-intl (merge logic carries), `src/lib/head.ts` + `src/lib/seo-meta.ts` replace `generateMetadata` (build-time + client), `/blog` pre-rendered from build-time slugs. Legacy Next sites keep the ISR/`generateMetadata` path. The prior Next-only entries below are superseded for new builds.
- [ ] **Step 2: Verify** `grep -nE "2026-06-21|Vite|VITE_CMS|src/lib/cms-content" "agents/CMS Connector - Website/LEARNINGS.md"` → present.

---

## Self-Review
- scan.py default → VITE_ (Task 1). ✓
- prompts.py t()-agnostic + Vite locale paths (Task 2). ✓
- 4-integration.md vite-react branches: content + draft fetch + SEO-area (Task 3). ✓
- AGENTS.md vite-react contracts (Task 4). ✓
- LEARNINGS append (Task 5). ✓
- Multi-framework preserved (every task ADDS a vite-react branch beside next). ✓
- SEO/GEO agent untouched; "NEVER provision seo_*" intact. ✓
- Vite paths verbatim-match the shipped builder. ✓
