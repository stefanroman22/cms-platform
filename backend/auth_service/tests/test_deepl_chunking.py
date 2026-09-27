import json
from unittest.mock import MagicMock, patch

from auth_service.translation.deepl import DeepLProvider


def _fake_urlopen(sent):
    def _open(req):
        body = json.loads(req.data.decode())
        sent.append(len(req.data))
        resp = MagicMock()
        resp.__enter__.return_value.read.return_value = json.dumps(
            {"translations": [{"text": f"T:{t}"} for t in body["text"]]}
        ).encode()
        return resp

    return _open


def test_large_batches_are_split_and_order_preserved():
    texts = [f"<p>{i}:" + ("é" * 30_000) + "</p>" for i in range(8)]  # ~480 KB total
    sent = []
    with patch(
        "auth_service.translation.deepl.urllib.request.urlopen", side_effect=_fake_urlopen(sent)
    ):
        out = DeepLProvider(api_key="k:fx").translate(texts, source="en", target="de", fmt="html")
    assert out == [f"T:{t}" for t in texts]
    assert len(sent) > 1
    assert all(size <= 110 * 1024 for size in sent)


def test_small_batch_is_one_request():
    sent = []
    with patch(
        "auth_service.translation.deepl.urllib.request.urlopen", side_effect=_fake_urlopen(sent)
    ):
        DeepLProvider(api_key="k:fx").translate(["a", "b"], source="en", target="de")
    assert len(sent) == 1
