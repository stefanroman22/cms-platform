import json
from unittest.mock import patch

import pytest

from auth_service.translation import get_provider
from auth_service.translation.deepl import DeepLProvider


class _FakeResp:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode()

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_free_key_uses_free_endpoint():
    p = DeepLProvider(api_key="abc:fx")
    assert p.url.startswith("https://api-free.deepl.com")


def test_pro_key_uses_pro_endpoint():
    p = DeepLProvider(api_key="abc")
    assert p.url.startswith("https://api.deepl.com")


def test_missing_key_raises():
    with pytest.raises(RuntimeError):
        DeepLProvider(api_key="")


def test_translate_sends_batch_and_restores_placeholders():
    p = DeepLProvider(api_key="k:fx")
    captured = {}

    def _fake_urlopen(req):
        captured["body"] = json.loads(req.data.decode())
        # DeepL echoes the (masked) text with a word translated, sentinels intact
        return _FakeResp(
            {
                "translations": [
                    {"text": t.replace("Welcome", "Welkom")} for t in captured["body"]["text"]
                ]
            }
        )

    with patch("auth_service.translation.deepl.urllib.request.urlopen", _fake_urlopen):
        out = p.translate(["Welcome © {year}"], source="en", target="nl", fmt="text")

    assert out == ["Welkom © {year}"]  # placeholder restored
    assert captured["body"]["target_lang"] == "NL"
    assert captured["body"]["source_lang"] == "EN"
    assert "{year}" not in captured["body"]["text"][0]  # masked on the wire
    assert "tag_handling" not in captured["body"]  # absent for fmt="text"


def test_translate_target_en_maps_to_en_gb():
    p = DeepLProvider(api_key="k:fx")
    captured = {}

    def _cap(req):
        captured["b"] = json.loads(req.data.decode())
        return _FakeResp({"translations": [{"text": "x"}]})

    with patch("auth_service.translation.deepl.urllib.request.urlopen", _cap):
        p.translate(["x"], source="nl", target="en", fmt="text")
    assert captured["b"]["target_lang"] == "EN-GB"


def test_empty_input_returns_empty_without_network():
    p = DeepLProvider(api_key="k:fx")
    assert p.translate([], source="en", target="nl") == []


def test_registry_exposes_deepl():
    with patch.dict("os.environ", {"DEEPL_API_KEY": "k:fx"}):
        assert get_provider("deepl").name == "deepl"


def test_html_fmt_sets_tag_handling():
    p = DeepLProvider(api_key="k:fx")
    captured = {}

    def _cap(req):
        captured["b"] = json.loads(req.data.decode())
        return _FakeResp({"translations": [{"text": "x"}]})

    with patch("auth_service.translation.deepl.urllib.request.urlopen", _cap):
        p.translate(["x"], source="en", target="nl", fmt="html")
    assert captured["b"]["tag_handling"] == "html"


def test_translate_raises_on_count_mismatch():
    p = DeepLProvider(api_key="k:fx")

    def _short(req):
        return _FakeResp({"translations": [{"text": "only one"}]})

    with patch("auth_service.translation.deepl.urllib.request.urlopen", _short):
        with pytest.raises(RuntimeError):
            p.translate(["a", "b"], source="en", target="nl")
