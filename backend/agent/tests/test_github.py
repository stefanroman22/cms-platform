import json
from unittest.mock import MagicMock, patch

import pytest

from .. import github as gh


@pytest.fixture
def fake_urlopen():
    with patch.object(gh, "urlopen") as mock:
        yield mock


def _resp(data: dict):
    m = MagicMock()
    m.read.return_value = json.dumps(data).encode()
    m.__enter__ = lambda s: s
    m.__exit__ = lambda s, *a: None
    return m


def test_create_branch_from_main(fake_urlopen):
    # First call: get main ref -> sha
    # Second call: get new-branch ref (branch_exists check - 404)
    # Third call: create new ref
    import urllib.error

    not_found = urllib.error.HTTPError(url="", code=404, msg="not found", hdrs=None, fp=None)
    fake_urlopen.side_effect = [
        not_found,  # branch_exists returns False
        _resp({"object": {"sha": "abc123"}}),  # main ref
        _resp({"ref": "refs/heads/cms-preview"}),  # create ref
    ]

    gh.create_branch("tok", "lauriand/portfolio", "cms-preview", from_branch="main")

    assert fake_urlopen.call_count == 3
    # Verify create payload is the 3rd call
    create_req = fake_urlopen.call_args_list[2][0][0]
    body = json.loads(create_req.data.decode())
    assert body["ref"] == "refs/heads/cms-preview"
    assert body["sha"] == "abc123"


def test_branch_exists_returns_true_when_present(fake_urlopen):
    fake_urlopen.return_value = _resp({"object": {"sha": "xyz"}})
    assert gh.branch_exists("tok", "lauriand/portfolio", "cms-preview") is True


def test_branch_exists_returns_false_on_404(fake_urlopen):
    import urllib.error

    err = urllib.error.HTTPError(
        url="", code=404, msg="not found", hdrs=None, fp=None,
    )
    fake_urlopen.side_effect = err

    assert gh.branch_exists("tok", "lauriand/portfolio", "cms-preview") is False


def test_create_branch_skips_when_branch_exists(fake_urlopen):
    # branch_exists returns True -> no create call
    fake_urlopen.return_value = _resp({"object": {"sha": "abc"}})

    gh.create_branch("tok", "lauriand/portfolio", "cms-preview", from_branch="main")

    # Only 1 call: the branch_exists check. No create call.
    assert fake_urlopen.call_count == 1
