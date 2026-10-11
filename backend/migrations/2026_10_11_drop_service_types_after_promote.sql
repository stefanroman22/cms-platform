-- backend/migrations/2026_10_11_drop_service_types_after_promote.sql
-- NOT YET APPLIED. Apply ONLY after the service-types removal has been promoted
-- to main: the code on main still embeds `service_types(name, icon[, schema])`
-- in every service query, and dropping the table first 500s the dashboard's
-- service list, editor and save.
--
-- The service-type catalogue now lives in code
-- (backend/auth_service/services/service_types.py: slug → name + icon). The
-- foreign key that guarded project_services.service_type_slug is replaced by a
-- CHECK over the same slugs; keep the two lists in sync. 'theme' is listed
-- ahead of its SERVICE_TYPES entry because the theme work (feat/theme-media)
-- adds it as a service_types row, which may be applied before this drop.

alter table public.project_services
  add constraint project_services_service_type_slug_check
  check (service_type_slug in (
    'email_config', 'file_download', 'floor_plan', 'gallery', 'image',
    'key_value', 'repeater', 'text_block', 'theme', 'video'
  ));

alter table public.project_services
  drop constraint project_services_service_type_slug_fkey;

drop table public.service_types;
