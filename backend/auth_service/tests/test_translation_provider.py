import pytest

from auth_service.translation import NullProvider, get_provider


def test_null_provider_echoes_input():
    p = NullProvider()
    assert p.name == "null"
    assert p.translate(["a", "b"], source="en", target="nl") == ["a", "b"]


def test_get_provider_defaults_to_null(monkeypatch):
    monkeypatch.delenv("TRANSLATION_PROVIDER", raising=False)
    assert get_provider().name == "null"


def test_get_provider_explicit_null():
    assert get_provider("null").name == "null"


def test_get_provider_reads_env(monkeypatch):
    monkeypatch.setenv("TRANSLATION_PROVIDER", "null")
    assert get_provider().name == "null"


def test_get_provider_unknown_raises():
    with pytest.raises(ValueError):
        get_provider("does-not-exist")
