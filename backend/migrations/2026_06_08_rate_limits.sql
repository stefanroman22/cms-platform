-- 2026-06-08 — Postgres-backed shared rate limiter + login lockout.
--
-- The in-memory slowapi limiter resets per Vercel serverless invocation and is not
-- shared across warm instances (SEC-010), so brute-force / abuse limits were
-- effectively N×limit. This adds a shared fixed-window counter in Postgres, used
-- for per-account login lockout (SEC-011/SEC-020) and public-endpoint limits
-- (SEC-012 and the booking/translation low findings).
--
-- One row per bucket (bucket is the PK; the row is overwritten each window), so the
-- table does not grow per request — only per distinct client/account. All access is
-- via the service-role key; the functions are SECURITY DEFINER with a pinned
-- search_path and are NOT executable by anon/authenticated (lesson from SEC-004).

create table if not exists public.rate_limits (
  bucket       text primary key,
  window_start timestamptz not null,
  count        integer not null
);

alter table public.rate_limits enable row level security;
revoke all on table public.rate_limits from anon, authenticated;

-- Atomic fixed-window increment. Returns TRUE if the hit is allowed (count <= limit).
create or replace function public.rate_limit_hit(p_bucket text, p_limit integer, p_window_seconds integer)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_window_start timestamptz := to_timestamp(floor(extract(epoch from now()) / p_window_seconds) * p_window_seconds);
  v_count integer;
begin
  insert into public.rate_limits as rl (bucket, window_start, count)
  values (p_bucket, v_window_start, 1)
  on conflict (bucket) do update
    set count = case when rl.window_start = v_window_start then rl.count + 1 else 1 end,
        window_start = v_window_start
  returning rl.count into v_count;
  return v_count <= p_limit;
end;
$$;

-- Read-only check: is the bucket already at/over the limit in the current window?
-- (Does not increment — used to gate before a login password check.)
create or replace function public.rate_limit_over(p_bucket text, p_limit integer, p_window_seconds integer)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_window_start timestamptz := to_timestamp(floor(extract(epoch from now()) / p_window_seconds) * p_window_seconds);
  v_count integer;
begin
  select rl.count into v_count from public.rate_limits rl
  where rl.bucket = p_bucket and rl.window_start = v_window_start;
  return coalesce(v_count, 0) >= p_limit;
end;
$$;

-- Clear a bucket (e.g. on a successful login).
create or replace function public.rate_limit_reset(p_bucket text)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  delete from public.rate_limits where bucket = p_bucket;
end;
$$;

-- Housekeeping: drop buckets whose last window is older than the cutoff.
create or replace function public.rate_limit_gc(p_older_than_seconds integer default 604800)
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_deleted integer;
begin
  delete from public.rate_limits
  where window_start < now() - make_interval(secs => p_older_than_seconds);
  get diagnostics v_deleted = row_count;
  return v_deleted;
end;
$$;

revoke all on function public.rate_limit_hit(text, integer, integer) from public, anon, authenticated;
revoke all on function public.rate_limit_over(text, integer, integer) from public, anon, authenticated;
revoke all on function public.rate_limit_reset(text) from public, anon, authenticated;
revoke all on function public.rate_limit_gc(integer) from public, anon, authenticated;
grant execute on function public.rate_limit_hit(text, integer, integer) to service_role;
grant execute on function public.rate_limit_over(text, integer, integer) to service_role;
grant execute on function public.rate_limit_reset(text) to service_role;
grant execute on function public.rate_limit_gc(integer) to service_role;
