-- backend/migrations/2026_10_10_drop_unused_columns.sql
-- Drops two columns that no code (backend, frontend, agents, client sites)
-- reads or writes, on dev or main:
--   projects.api_key    — null on every row; its unique constraint goes with it.
--   bookings.party_size — never set (default 1), never read.

alter table public.projects drop column if exists api_key;
alter table public.bookings drop column if exists party_size;
