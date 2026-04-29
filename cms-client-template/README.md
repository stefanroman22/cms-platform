# CMS Client Template

Integration kit for connecting any website to the Roman Technologies CMS.

## What's in this directory

| File | Purpose |
|---|---|
| `cms.config.example.ts` | TypeScript config template — copy to `cms.config.ts` |
| `cms.config.example.json` | JSON config template — copy to `cms.config.json` |
| `lib/cms.ts` | Fetch helpers + React hook — copy to your project's `lib/` |
| `cms.types.example.ts` | Example of what `npm run cms:sync-types` generates |
| `scripts/sync-cms-types.mjs` | CLI script that generates TypeScript types from the CMS |

---

## Setup (any framework)

### 1. Copy the config

**TypeScript projects:**
```bash
cp cms.config.example.ts your-project/cms.config.ts
```

**JSON-only projects (Astro, plain JS):**
```bash
cp cms.config.example.json your-project/cms.config.json
```

### 2. Edit the config

```ts
// cms.config.ts
export const cmsConfig = {
    projectSlug: "your-project-slug",   // must match the slug in the CMS dashboard
    endpoint: "https://cms.romantechnologies.com/content",
    services: {
        hero:          "text_block",
        hero_image:    "image",
        contact_form:  "email_config",
        experience:    "repeater",      // items: [{ company, role, period, bullets[] }]
    },
} as const;
```

### 3. Copy `lib/cms.ts` into your project

```bash
cp lib/cms.ts your-project/lib/cms.ts
```

Update the import path at the top of `cms.ts` to point at your config:
```ts
import { cmsConfig } from "../cms.config";       // adjust if needed
import type { CMSContent } from "../cms.types";  // generated in step 4
```

### 4. Generate TypeScript types

Add to your `package.json`:
```json
{
  "scripts": {
    "cms:sync-types": "node scripts/sync-cms-types.mjs"
  }
}
```

Copy `scripts/sync-cms-types.mjs` to your project and run:
```bash
npm run cms:sync-types
```

This generates `cms.types.ts` in your project root with typed interfaces for every service.

---

## Usage by framework

### Next.js App Router (SSR + ISR)

```tsx
// app/page.tsx
import { getCMSContent } from '@/lib/cms'

export default async function HomePage() {
    const cms = await getCMSContent()   // Next.js ISR: revalidates every 60 s

    return <h1>{cms.content.hero?.title}</h1>
}
```

`getCMSContent()` passes `next: { revalidate: 60 }` — Next.js will cache the response and
revalidate in the background every 60 seconds, matching the CMS `Cache-Control` header.

### React / Vite (CSR hook with fallback)

```tsx
// src/views/HeroView.tsx
import { useCMSContent, withFallback } from '@/lib/cms'
import { FALLBACK_TITLE } from '@/constants/hero'

export function HeroView() {
    const { data: cms, loading } = useCMSContent()

    const title = withFallback(cms?.content.hero?.title, FALLBACK_TITLE)

    return <h1>{title}</h1>
}
```

`useCMSContent()` includes a 60-second module-level cache — multiple components calling the
hook in the same render will only fire one request.

`withFallback(live, fallback)` returns `live` if it exists, otherwise `fallback`. This keeps
your site functional even when the CMS is unreachable.

### Astro / plain SSR (fresh fetch, no caching)

```ts
// src/pages/index.astro (frontmatter)
import { getCMSContentFresh } from '../lib/cms'

const cms = await getCMSContentFresh()
const title = cms.content.hero?.title ?? 'Fallback Title'
```

### Accessing typed service content

```ts
import { getService, withFallback } from '@/lib/cms'

const hero = getService(cms, 'hero')        // typed as CMSContent["content"]["hero"]
const title = withFallback(hero?.title, 'Default Title')
```

---

## Repeater services

Repeater services store arrays of structured items. The schema is defined when the service
is created in the CMS dashboard.

```ts
// cms.config.ts
services: {
    experience: "repeater",    // items: [{ company, role, period, bullets[] }]
    projects_list: "repeater", // items: [{ name, description, tags[], url, repo }]
}
```

Consuming repeater content in a component:

```tsx
const { data: cms } = useCMSContent()

const cmsItems = (cms?.content.experience as { items?: Record<string, unknown>[] } | undefined)?.items
const experience = cmsItems
    ? cmsItems.map((item, i) => ({
        id:      `exp-${i}`,
        company: String(item.company ?? ''),
        role:    String(item.role    ?? ''),
        period:  String(item.period  ?? ''),
        bullets: Array.isArray(item.bullets) ? (item.bullets as string[]) : [],
    }))
    : FALLBACK_EXPERIENCE   // fall back to hard-coded data
```

---

## Contact form submission

Forms POST to the CMS forms endpoint — no email credentials needed in your website:

```ts
const FORMS_ENDPOINT =
    'https://cms.romantechnologies.com/forms/your-project-slug/contact_form'

async function submitForm(form: { name: string; email: string; message: string }) {
    const res = await fetch(FORMS_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
    })
    if (!res.ok) throw new Error('Form submission failed')
}
```

The destination email is configured in the CMS dashboard under the `email_config` service —
it is never exposed to the browser.

---

## Auto-generating the config (AI agent)

Instead of writing `cms.config.ts` by hand, run the CMS scanner agent against your website
source code:

```bash
python "agents/CMS Connector - Website/scan.py" \
    --dir path/to/your-website/src \
    --slug your-project-slug \
    --out ./output \
    --provision \
    --api-url https://cms.romantechnologies.com \
    --api-token YOUR_JWT_TOKEN
```

The agent reads your source files, identifies hard-coded content, and:
1. Writes `output/cms.config.json` — ready to copy into your project
2. Writes `output/cms-provision.json` — full manifest with initial content seeds
3. If `--provision` is passed: automatically creates all services in the CMS via the API

---

## Service types reference

| Type | Stores | Use for |
|---|---|---|
| `text_block` | `{ title, body }` | Hero sections, about blurbs, page copy |
| `image` | `{ url, alt }` | Hero images, logos, banners |
| `gallery` | `{ items: [{ url, alt }] }` | Photo galleries |
| `key_value` | `{ entries: { key: value } }` | CV data, social links, contact info |
| `repeater` | `{ _schema: [...], items: [...] }` | Experience entries, projects, hobbies |
| `email_config` | destination email (not public) | Contact forms |
| `video` | `{ url, poster }` | Embedded or uploaded videos |
| `file_download` | `{ url, filename }` | PDFs, brochures |
| `floor_plan` | `{ url, alt }` | Restaurant/venue floor plans |
