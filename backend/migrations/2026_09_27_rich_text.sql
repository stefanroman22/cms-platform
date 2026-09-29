-- 2026-09-27 rich text (ADR-0010). Additive: old code ignores the column.
-- Existing projects start at 0 (legacy behaviour) and are flipped to 1 one at a
-- time by backend/scripts/migrate_rich_text.py after their site ships the kit.
-- Projects created after this migration default to 1.
alter table projects add column if not exists rich_text_version smallint not null default 0;
alter table projects alter column rich_text_version set default 1;
alter table projects drop constraint if exists projects_rich_text_version_check;
alter table projects add constraint projects_rich_text_version_check check (rich_text_version in (0, 1));

update service_types
   set schema = jsonb_set(schema, '{fields,title,type}', '"inline"')
 where slug = 'text_block';
