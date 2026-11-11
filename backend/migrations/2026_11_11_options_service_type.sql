-- 2026-11-11 options service type (ADR-0013). Additive: widens the
-- project_services.service_type_slug CHECK with 'options' ("Display Options");
-- every existing row still passes. Its content is validated by
-- services/content_structure.py (normalize_options).
-- Apply BEFORE the code that creates options services ships; keep this list in
-- sync with SERVICE_TYPES in backend/auth_service/services/service_types.py.

alter table public.project_services
  drop constraint project_services_service_type_slug_check;

alter table public.project_services
  add constraint project_services_service_type_slug_check
  check (service_type_slug in (
    'email_config', 'file_download', 'floor_plan', 'gallery', 'image',
    'key_value', 'options', 'repeater', 'text_block', 'theme', 'video'
  ));
