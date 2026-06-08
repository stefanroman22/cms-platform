# Bookings — Appointments Management (Phase 2b) Plan

> Design + plan combined (delegated build per user "do it all"). Builds on Phase 1 (foundation) + 2a (config dashboard). No DB migration.

**Goal:** Let the owner see and manage their appointments from the dashboard — a filterable list + a detail drawer with manual cancel / reschedule / mark-no-show / mark-completed actions, plus "New appointment" (book on behalf of a customer).

**Architecture:** Extend the 2a owner surface — add appointment endpoints to `routers/booking_admin.py` and helpers to `services/booking_admin_repo.py`, reusing `booking_repo` (insert/update), `booking_availability.free_resource_ids_at` (resource assignment), and `booking_tenant.load_tenant_by_id` (tenant tz/granularity). Owner actions bypass policy windows (owner override) and write `booking_audit_log`. Frontend adds an "Appointments" tab to `BookingsSection`.

## Backend

### Repo helpers — append to `backend/auth_service/services/booking_admin_repo.py`
```python
def list_appointments(tenant_id: str, *, status: str | None, service_id: str | None,
                      resource_id: str | None, date_from: str | None, date_to: str | None) -> list[dict]:
    sb = get_supabase_admin()
    q = (sb.table("bookings")
         .select("id, status, start_utc, end_utc, reschedule_count, notes, source, "
                 "service_id, resource_id, customer_id, "
                 "booking_customers(name, email, phone, timezone), "
                 "booking_services(name), booking_resources(name)")
         .eq("tenant_id", tenant_id))
    if status:
        q = q.eq("status", status)
    if service_id:
        q = q.eq("service_id", service_id)
    if resource_id:
        q = q.eq("resource_id", resource_id)
    if date_from:
        q = q.gte("start_utc", date_from)
    if date_to:
        q = q.lte("start_utc", date_to)
    return (q.order("start_utc", desc=True).execute()).data or []


def get_booking(tenant_id: str, booking_id: str) -> dict | None:
    sb = get_supabase_admin()
    res = (sb.table("bookings").select("*").eq("tenant_id", tenant_id)
           .eq("id", booking_id).limit(1).execute())
    rows = res.data or []
    return rows[0] if rows else None
```

### Endpoints — append to `routers/booking_admin.py`
Use the existing `_tenant(project_slug, request)` helper for owner auth + tenant id. Add `booking_tenant`, `booking_repo`, `booking_availability` imports.

- `GET /projects/{slug}/bookings/appointments` (query: `status,service_id,resource_id,from,to`) → `{appointments: [...]}` flattening the embedded customer/service/resource names into `customer_name`, `customer_email`, `service_name`, `resource_name`.
- `POST /projects/{slug}/bookings/appointments` (status 201) body `AppointmentCreate {service_id, resource_id?, start_utc, customer{name,email,phone?,tz?}, note?}` → load tenant config (`booking_tenant.load_tenant_by_id`), load service (`booking_repo.load_service`), assign resource: if `resource_id` given use it, else `booking_availability.free_resource_ids_at(...)[0]` (use the tenant tz/granularity + service duration/buffers) — 409 if none free; compute guard; `booking_repo.upsert_customer`; `booking_repo.insert_booking(..., source="dashboard")` (catch `BookingConflict` → 409); audit `action="create" actor="owner"`. Return the booking row.
- `PATCH /projects/{slug}/bookings/appointments/{id}` body `AppointmentAction {action: "cancel"|"reschedule"|"no_show"|"complete", start_utc?, reason?}`:
  - load booking via `booking_admin_repo.get_booking` (404 if absent).
  - **cancel** → `booking_repo.update_booking(id, {"status":"cancelled","cancelled_at":now,"cancel_reason":reason})`; audit.
  - **no_show** → status `no_show`; audit. **complete** → status `completed`; audit.
  - **reschedule** → require `start_utc`; load service + tenant; assign a free resource excluding this booking (`booking_repo.busy_guard_intervals_by_resource(..., exclude_booking_id=id)` via the availability path, OR reuse the public `_free_resource_for` pattern — owner has no policy-window check); compute new start/end/guard; `update_booking` (catch conflict → 409); audit `action="reschedule" actor="owner"`.
  - Owner actions do NOT enforce policy windows (owner override) — note in audit payload.

Add Pydantic models `AppointmentCreate`, `AppointmentAction` to `models/booking_admin_schemas.py`.

### Tests — `backend/auth_service/tests/test_booking_appointments_router.py`
Patch `require_user`/`require_project_access` at `auth_service.routers.booking_admin.*` (as in 2a). Cover: list returns flattened rows; manual create assigns a resource + inserts (mock repo) → 201; create with no free resource → 409; cancel sets status cancelled (mock update); no_show/complete set status; reschedule with a free slot updates (mock) → 200; reschedule conflict → 409; unknown booking → 404; ownership 403 (require_project_access raises). Mock supabase per existing style.

## Frontend

### `components/dashboard/booking/AppointmentsManager.tsx` (+ `AppointmentDetailDrawer.tsx`, `NewAppointmentDrawer.tsx`)
- Wire into `BookingsSection` inner tab strip: add an **Appointments** tab (first tab) rendering `<AppointmentsManager projectSlug={slug} />`.
- Add API wrappers to `booking/api.ts`: `listAppointments(slug, filters)`, `createAppointment(slug, body)`, `actOnAppointment(slug, id, body)` — types matching the backend.
- **AppointmentsManager**: filter controls (status select, service select, resource select, date range) + a table/list (date·time in tenant tz, customer, service, resource, status badge). Row click → `AppointmentDetailDrawer`. "New appointment" button → `NewAppointmentDrawer`. Refresh-trigger after mutations (mirror `ServicesManager`).
- **AppointmentDetailDrawer** (mirror `LeadDetailDrawer`): shows details; action buttons — Cancel (with reason), Reschedule (date+slot picker → `/booking/{slug}/availability` public slots OR a simple datetime; reuse the slot fetch), Mark no-show, Mark completed. Calls `actOnAppointment`; surfaces 409 ("slot taken") inline; calls `onChanged` to refresh.
- **NewAppointmentDrawer**: service select → date/slot (fetch availability) → customer fields → create via `createAppointment`. 409 on slot-taken.
- Styling/conventions per 2a (`lib/styles.ts`, `motion/react`, cursor-pointer).

## Verify
- Backend: `pytest auth_service/tests/test_booking_appointments_router.py -v` green; full suite green.
- Frontend: `npx tsc --noEmit` clean; `npm test -- --run` green. (Build deferred to the end-of-push milestone.)
- No commit (per standing rule).
