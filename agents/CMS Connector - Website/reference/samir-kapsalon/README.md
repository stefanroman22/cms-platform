# samir-kapsalon reference (archived)

The samir-kapsalon client site (repo `stefanroman22/samir-kapsalon`, Vercel project
`samir-kapsalon`) was retired on 2026-11-24 to save platform usage. `phases/4-integration.md`
names its integration code as the canonical multilingual pattern, so the three files that
pattern lives in are kept here, copied unchanged from the repo's last `main` commit:

- `lib/cms-content.ts` — maps CMS services onto next-intl namespaces (multilingual reference)
- `lib/cms-site.ts` — site-level content (theme, page options, gallery)
- `lib/booking.ts` — the generated booking client (`getAvailabilityHorizon`, preload once)

They are reference only: nothing imports them, and they are not built or linted here.
