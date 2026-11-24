-- 2026-11-24 rate_limits: UNLOGGED + fillfactor 70, to cut Disk IO.
-- STATUS: NOT APPLIED
--
-- Why: since SEC-095 every public /content read (every client-site page view) runs
-- rate_limit_hit(), an UPDATE on this table. On a logged table each of those commits writes
-- WAL and waits for a WAL flush to disk, which spends the Supabase Disk IO budget
-- (alert 2026-11-24). An UNLOGGED table writes no WAL, so commits that touch only this
-- table skip the flush. fillfactor 70 leaves room on each page so the counter UPDATEs
-- can be HOT updates (no index writes; count/window_start are not indexed).
--
-- Trade-off: Postgres empties an unlogged table after a crash or failover. For a
-- fixed-window rate-limit counter that only means the counters restart at zero, the same
-- as a new window. The limiter is already fail-open (core/pg_rate_limit.py). Nothing else
-- references this table, and no code changes are needed.
--
-- Safe to apply at any time. SET UNLOGGED rewrites the table under a short exclusive lock;
-- the table is small (one row per bucket, GC'd nightly by gc-rate-limits).
-- Undo: alter table public.rate_limits set logged; alter table public.rate_limits reset (fillfactor);

-- fillfactor first: SET UNLOGGED rewrites the table, so the rewrite applies it to every page.
alter table public.rate_limits set (fillfactor = 70);
alter table public.rate_limits set unlogged;
