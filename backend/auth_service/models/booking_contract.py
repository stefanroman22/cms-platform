"""Machine-readable, versioned contract for the public create-booking payload.

This is the single source of truth that the `booking-client` SDK and the CMS
connector validate against. It is served verbatim by `GET /booking/{slug}/contract`
so a client form can be checked at provisioning time and the SDK can validate
before sending. Bump `BOOKING_CONTRACT_VERSION` whenever the required fields or
their shapes change in a non-backward-compatible way.
"""

from __future__ import annotations

# 1.1.0: `resource_id` is now honored on create (customer-chosen barber) and the
# public availability/resources endpoints accept a resource filter. Still optional
# and backward compatible — clients that omit it get auto-assignment as before.
BOOKING_CONTRACT_VERSION = "1.1.0"

# Per-field type/format descriptors. Dotted keys describe nested customer fields.
BOOKING_CONTRACT = {
    "version": BOOKING_CONTRACT_VERSION,
    "required": ["service_id", "start_utc", "customer.name", "customer.email"],
    "fields": {
        "service_id": {"type": "string"},
        "start_utc": {"type": "string", "format": "date-time"},
        "resource_id": {"type": "string", "required": False},
        "note": {"type": "string", "required": False},
        "customer.name": {"type": "string"},
        "customer.email": {"type": "string", "format": "email"},
        "customer.phone": {"type": "string", "required": False},
        "customer.locale": {"type": "string", "required": False},
        "customer.tz": {"type": "string", "required": False},
    },
}
