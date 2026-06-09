"""ServiceCreateRequest accepts snake_case service keys/type slugs (the canonical
content-model format, also used as next-intl namespaces) while still rejecting
storage-unsafe characters. Regression: a hyphen-only slug pattern wrongly rejected
`text_block` / `general_brand_name`, blocking ALL service provisioning."""

import pytest
from pydantic import ValidationError

from auth_service.models.schemas import ServiceCreateRequest


def test_accepts_snake_case_key_and_type():
    m = ServiceCreateRequest(
        service_type_slug="text_block", service_key="general_brand_name", label="Brand name"
    )
    assert m.service_key == "general_brand_name"
    assert m.service_type_slug == "text_block"


def test_accepts_plain_lowercase_and_digits():
    m = ServiceCreateRequest(service_type_slug="repeater", service_key="reviews2", label=None)
    assert m.service_key == "reviews2"


@pytest.mark.parametrize("bad", ["a/b", "a.b", "Service_Key", "with space", "a-b", "", "x" * 65])
def test_rejects_storage_unsafe_or_uppercase(bad):
    with pytest.raises(ValidationError):
        ServiceCreateRequest(service_type_slug="text_block", service_key=bad)
