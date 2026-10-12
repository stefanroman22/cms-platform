-- 2026-10-11 theme service type (ADR-0011). Additive: a project has at most one
-- `theme` service (enforced by POST /projects/{slug}/services); its content is
-- validated by services/theme.py, so the type declares no fields here.
-- Apply BEFORE 2026_10_11_drop_service_types_after_promote.sql: production still
-- has the service_types table + FK until that drop runs (whose CHECK already
-- lists 'theme'); the code catalogue is services/service_types.py.
insert into service_types (slug, name, description, icon, schema)
values ('theme', 'Theme', 'Site fonts, brand colours and surfaces (ADR-0011)', 'Palette', '{"fields": {}}'::jsonb)
on conflict (slug) do nothing;
