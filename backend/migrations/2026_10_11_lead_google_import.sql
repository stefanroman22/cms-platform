-- 2026_10_11_lead_google_import.sql — ADR-0012: import a lead from a Google Maps listing.
-- Additive only. Apply by hand (scripts/apply_supabase_migration.py or Supabase MCP)
-- before or with the code that selects these columns.

alter table public.leads
    add column if not exists google_place_id    text,
    add column if not exists google_imported_at timestamptz,
    add column if not exists business_status    text,
    add column if not exists primary_type       text,
    add column if not exists types              text[] not null default '{}'::text[],
    add column if not exists price_level        text,
    add column if not exists social_links       jsonb not null default '{}'::jsonb;

-- One lead per Google place; NULL for manual leads, so a partial index.
create unique index if not exists leads_google_place_id_uidx
    on public.leads (google_place_id)
    where google_place_id is not null;

comment on column public.leads.google_place_id is
    'Places API place ID. The only Google value we may store indefinitely; used to re-import.';
comment on column public.leads.social_links is
    'Full social map {facebook,instagram,tiktok,linkedin,youtube,x,pinterest,whatsapp}: url. facebook_url/instagram_url mirror two of its keys.';
comment on column public.leads.price_level is
    'Google priceLevel without the PRICE_LEVEL_ prefix, lowercase (free|inexpensive|moderate|expensive|very_expensive).';

-- Public bucket for imported listing photos. Served by public URL; writes go through the
-- service-role backend only (no storage policies needed).
insert into storage.buckets (id, name, public)
values ('lead-photos', 'lead-photos', true)
on conflict (id) do nothing;

-- Monthly Google import counter (ADR-0012). Separate from rate_limits so the nightly
-- rate_limit_gc never resets it; keyed by calendar month (UTC).
create table if not exists public.google_import_usage (
    month date primary key,
    count integer not null default 0
);
alter table public.google_import_usage enable row level security;

-- Atomically count one import against this month; false (and no increment) when the
-- month is already at p_limit.
create or replace function public.google_import_hit(p_limit integer)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
    m date := date_trunc('month', now() at time zone 'utc')::date;
    c integer;
begin
    insert into public.google_import_usage (month, count) values (m, 0)
    on conflict (month) do nothing;
    update public.google_import_usage
       set count = count + 1
     where month = m and count < p_limit
    returning count into c;
    return c is not null;
end;
$$;

-- Read-only check (no increment).
create or replace function public.google_import_over(p_limit integer)
returns boolean
language sql
security definer
set search_path = public
as $$
    select coalesce(
        (select count >= p_limit from public.google_import_usage
          where month = date_trunc('month', now() at time zone 'utc')::date),
        false);
$$;

revoke all on function public.google_import_hit(integer) from public, anon, authenticated;
revoke all on function public.google_import_over(integer) from public, anon, authenticated;
grant execute on function public.google_import_hit(integer) to service_role;
grant execute on function public.google_import_over(integer) to service_role;

-- Backfill: existing leads get social_links from their legacy columns.
update public.leads
   set social_links = jsonb_strip_nulls(jsonb_build_object(
           'facebook', nullif(btrim(facebook_url), ''),
           'instagram', nullif(btrim(instagram_url), '')))
 where social_links = '{}'::jsonb
   and (nullif(btrim(facebook_url), '') is not null or nullif(btrim(instagram_url), '') is not null);
