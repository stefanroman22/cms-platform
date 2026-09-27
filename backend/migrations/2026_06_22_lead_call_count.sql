-- 2026-06-22: per-lead call counter
--
-- leads.call_count — how many times the business has been called (0-3),
-- editable via the leads dashboard dropdown. Additive, default 0, so every
-- existing row backfills to "not called" with no behaviour change.

alter table public.leads
    add column if not exists call_count integer not null default 0;
