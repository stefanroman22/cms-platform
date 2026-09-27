# ADR-0004: The backend is one stateless serverless function

Status: Accepted
Date: 2026-09-27

## Context

The backend has low, bursty traffic and one operator. Vercel hosts the frontend already, and
hosting FastAPI on Vercel too means no server to patch, no process manager and one billing account.
The price is that every request may run in a fresh or a different instance.

## Decision

- FastAPI runs as a single Vercel Python function: `backend/vercel.json` routes every path to
  `vercel_entry.py` via `@vercel/python`.
- Nothing that must hold across requests is kept in process memory. Shared state lives in Postgres.
  Rate limiting uses the Postgres limiter (`core/pg_rate_limit.py`), because the in-memory slowapi
  limiter "resets per Vercel serverless invocation and is not shared across warm instances, so its
  limits were effectively N×limit".
- Scheduled work runs in the database, not in the app: Supabase `pg_cron` calls a backend HTTP
  endpoint through `pg_net`, authenticated with a shared secret
  (`migrations/2026_06_05_booking_reminders_cron.sql`, `POST /booking/cron/reminders`).
- Security headers are set at the platform layer in `backend/vercel.json`.

## Consequences

- No servers to run. It scales to zero, and a deploy is just a Vercel deployment.
- Cold starts and per-request limits apply. Long jobs must be split into short HTTP-triggered steps.
- Some booking writes and the marketing contact form still use the in-memory limiter. This is a
  known gap (SEC-058/059 in `security/`), not a pattern to copy.
- Vercel installs `backend/requirements.txt`, not the hashed lock (see the check in `make lint`).
- Do NOT: add in-memory caches, counters, locks or queues that are assumed to be shared; add
  background threads, `asyncio` tasks that outlive the request, or in-app schedulers
  (APScheduler, Celery beat); or rely on the local filesystem between requests. Moving the backend
  to a long-running server needs a new ADR.
