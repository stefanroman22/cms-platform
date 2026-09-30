# Dashboard speed: faster load, save and typing in the CMS editor

Date: 2026-09-30. Status: approved for implementation (standing autonomy).

## Goal

Editing content in the dashboard must feel instant: opening a service, switching language, typing in
rich-text fields, and saving. Saving must also stop losing edits.

## What we measured (2026-09-30)

- Supabase `xeluydwpgiddbamysgyu` is in **eu-west-1 (Dublin)**.
- Both Vercel projects run their functions in **iad1 (Washington DC)**. Responses carry
  `X-Vercel-Id: fra1::iad1::…`. Neither `backend/vercel.json` nor the frontend sets `regions`.
- As a result, every Supabase query (one PostgREST HTTP call) crosses the Atlantic, at about 80 ms
  RTT. The public content GET takes 0.5–1.5 s, and `/health` alone takes 0.33–0.54 s from Europe.
- A save on a single-locale project makes about 8 sequential Supabase calls:
  1. session
  2. project
  3. rate limit (multi-locale projects only)
  4. service
  5. rows
  6. upsert
  7. session again, inside `get_service`
  8. project again
  9. service re-read
- On a multi-locale project the save also runs DeepL for each other locale, **one after another**,
  before it responds.
- The frontend then **throws away** the PUT response and GETs the service again. That changes
  `last_updated`, which **remounts every editor**. Focus, cursor and undo history are lost, and so is
  anything typed while the save was in flight.
- On each keystroke, every `RichTextEditor` on the page calls `editor.setOptions()`. `useEditor` gets
  new `extensions`/`editorProps`/`content` objects on every render, and TipTap compares them by
  identity. A repeater with N items therefore does N ProseMirror state updates per keystroke.

## Decision: fix the path, not a cache in front of it

**No Redis.** It would not help, for these reasons:

- Once the functions sit next to the database, a Supabase call costs about 2–5 ms. A Redis call would
  cost about the same. The delay comes from geography and from how many calls a request makes, not
  from the speed of each call.
- ADR-0004 forbids in-process caches. A shared Redis would need a new ADR, a new paid-tier service,
  a new secret, and cache invalidation on every write. Stale content right after a save is exactly the
  kind of "buggy" behaviour we are trying to remove.

**Client caching already exists** (`hooks/useQuery.ts` + `lib/cache.ts`, stale-while-revalidate). We
keep it and fix how the editor uses it: use the save response, invalidate the right keys, and
prefetch on hover.

## Design

### 1. Region co-location (largest win)

- Pin both Vercel projects to **`dub1` (Dublin)**, in the same AWS region as Supabase eu-west-1.
  - `backend/vercel.json` gets `"regions": ["dub1"]`.
  - A new `frontend/vercel.json` gets `{"regions": ["dub1"]}`.
- This is free and needs no code change. It also brings the Next proxy → FastAPI hop and the DeepL
  calls (DeepL is hosted in the EU) close together.
- Record the decision in ADR-0004.

### 2. Backend save path

- `save_service` stops calling the `get_service` route function, which re-ran auth and the project
  lookup. It calls a new helper, `_service_detail(project, user, service_key, loc)`, that does only
  the one service select and the flattening. `get_service` = auth + project + the same helper.
  Behaviour and response shape are unchanged. This also fixes the bearer-token (connector) save
  re-read, which went through the cookie-only `require_user`.
- Default-locale save on a multi-locale project: **translate all other locales in parallel**, using a
  `ThreadPoolExecutor` scoped to the request (it is created and joined inside the handler, so it does
  not outlive the request, per ADR-0004).
  - Each worker gets deep copies of its inputs.
  - Upserts still run in the request thread, in `locales` order, so DB writes stay sequential and
    deterministic.
  - Per-locale failure isolation is unchanged: a locale that fails is logged and skipped.
- `list_services` fetches embedded `content_entries` only for `[loc, default_locale]` instead of every
  locale. This cuts the payload about 6× on it-global-services.

### 3. Frontend save flow (`ServiceEditor.tsx`)

- `saveContent` returns the `ServiceDetail` from the PUT. On success:
  - `cache.set(cacheKey, saved)`, with no second GET.
  - Invalidate the other locales' detail keys for this service, the `services:{slug}` grid list, and
    the `status:{slug}` publish-bar key.
- **No remount after your own save.** The editor key becomes a `editorRevision` counter. It is bumped
  only when `last_updated` changes for a reason other than our own save: re-translate, or a
  background revalidation while the editor is clean.
- **Edits made during a save are kept.** A change counter snapshots at save start. On success the
  draft is cleared only if nothing changed since then; otherwise it stays dirty.
- **No typing into the wrong locale.** While a locale switch is loading, the editor wrapper is
  `inert` and Save is disabled.
- **Ctrl/Cmd+S saves.**
- `PreviewPublishBar` subscribes to `status:{slug}` in the cache and refreshes immediately after a
  save or re-translate, so the Publish button enables right away.

### 4. Typing performance (`RichTextEditor.tsx`)

- Memoise `extensions` (by mode and placeholder) and `editorProps` (by mode, label and id).
- Freeze `content` to the mount-time value, since the component is uncontrolled.
- With these, TipTap's `compareOptions` passes and `setOptions`/`updateState` stop running on every
  parent render.

### 5. Perceived speed: prefetch

- Hovering or focusing a service card's Edit link prefetches that service's detail.
- Hovering or focusing a locale tab prefetches that locale.
- Both use `cache.prefetch`, which already dedupes in-flight requests and skips entries fresher than
  5 minutes.
- The fetch helper moves to `components/dashboard/serviceApi.ts`, so the card, the tabs and the
  editor share the fetcher and the cache-key format.

## Out of scope (noted, not done)

- Lazy-loading TipTap out of the project bundle.
- Status endpoint redundant `projects` read.
- Publish N+1.
- Public `/content` edge caching.
- Removing nested `AnimatePresence mode="wait"` delays.

These are candidates for a follow-up once the above is measured.

## Success criteria

- Backend responses show `X-Vercel-Id: …::dub1::…`.
- Warm `/health` responds in under 150 ms from the EU.
- Warm single-locale save responds in under 400 ms.
- After Save, the editor keeps focus and cursor, and text typed during the save stays and is marked
  unsaved.
- No second GET after a save (checked in the network tab and by a unit test).
- Typing in a repeater with several rich fields: `editor.setOptions` is not called on parent
  re-render (unit test).
- `make ci` is green.
