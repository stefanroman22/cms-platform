# backend/auth_service/tests/test_booking_integration.py
"""DB-backed booking guarantee: no double-book under concurrency (the real
btree_gist exclusion constraint). Skipped unless RUN_BOOKING_INTEGRATION=1 and
the migration is applied (it writes/cancels rows in a dedicated test tenant).

Cross-tenant isolation is covered by always-run unit tests: every booking_repo
query filters by an explicit tenant_id, and public routes resolve the tenant
server-side from the slug (see test_booking_slug_router.py::
test_tenant_isolation_route_scopes_to_resolved_tenant and ::test_unknown_slug_404)."""

import concurrent.futures
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from auth_service.services import booking_repo
from auth_service.services.booking_repo import BookingConflict

UTC = ZoneInfo("UTC")
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_BOOKING_INTEGRATION") != "1",
    reason="integration test; set RUN_BOOKING_INTEGRATION=1 after migration",
)

# The E2E test project seeded by the migration's instructions (see Task 11 notes).
TEST_TENANT = os.getenv("BOOKING_TEST_TENANT_ID", "")
TEST_SERVICE = os.getenv("BOOKING_TEST_SERVICE_ID", "")
TEST_RESOURCE = os.getenv("BOOKING_TEST_RESOURCE_ID", "")


def _insert(start):
    cid = booking_repo.upsert_customer(
        tenant_id=TEST_TENANT,
        name="IT",
        email="it@test.com",
        phone=None,
        locale="en",
        timezone="UTC",
    )
    return booking_repo.insert_booking(
        tenant_id=TEST_TENANT,
        service_id=TEST_SERVICE,
        resource_id=TEST_RESOURCE,
        customer_id=cid,
        customer_name="IT",
        start_utc=start,
        end_utc=start + timedelta(minutes=45),
        guard_start_utc=start,
        guard_end_utc=start + timedelta(minutes=45),
        manage_token_hash=os.urandom(8).hex(),
        source="api",
        notes=None,
    )


def test_concurrent_same_slot_only_one_wins():
    start = datetime(2099, 1, 1, 9, 0, tzinfo=UTC)
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(_insert, start) for _ in range(8)]
        for f in futs:
            try:
                results.append(f.result())
            except BookingConflict:
                results.append(None)
    assert sum(1 for r in results if r) == 1
    # cleanup
    for r in results:
        if r:
            booking_repo.update_booking(r, {"status": "cancelled"})
