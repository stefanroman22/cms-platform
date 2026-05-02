# E2E test suite

Playwright + headless Chromium against the deployed Vercel projects.
Backed by two dedicated Supabase users + one isolated e2e project that
`scripts/seed_e2e.py` provisioned.

## First-time setup (laptop)

```bash
cd e2e
npm install
npx playwright install --with-deps chromium
cp .env.example .env.local
# paste E2E_USER_PASSWORD + E2E_ADMIN_PASSWORD from the password manager
```

## Run

```bash
npm test                  # headless
npm run test:headed       # see the browser
npm run test:ui           # interactive mode
npm run report            # last run's HTML report
```

## Targeting a different backend

Set `E2E_BASE_URL_FRONTEND` and `E2E_BASE_URL_BACKEND` in `.env.local`. Tests
hit those URLs verbatim — they don't spin up servers.

## Failure debugging

- Failed runs save trace + screenshot + video to `test-results/`.
- `npx playwright show-trace test-results/.../trace.zip` opens the timeline.
