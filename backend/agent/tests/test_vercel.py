import json
from unittest.mock import MagicMock, patch

import pytest

from .. import vercel


@pytest.fixture
def fake_urlopen():
    with patch.object(vercel, "urlopen") as mock:
        yield mock


def _json_response(data: dict, status: int = 200):
    m = MagicMock()
    m.read.return_value = json.dumps(data).encode()
    m.__enter__ = lambda s: s
    m.__exit__ = lambda s, *a: None
    m.status = status
    return m


def test_find_project_by_github_repo_returns_id_if_exists(fake_urlopen):
    # Vercel API returns `link.org` + `link.repo` separately (not combined)
    fake_urlopen.return_value = _json_response({
        "projects": [
            {
                "id": "prj_abc",
                "link": {
                    "type": "github",
                    "org": "lauriand",
                    "repo": "portfolio",
                    "productionBranch": "master",
                },
            },
        ]
    })

    result = vercel.find_project_by_repo("tok", "lauriand/portfolio")
    assert result == {"id": "prj_abc", "production_branch": "master"}


def test_find_project_by_github_repo_returns_none_when_missing(fake_urlopen):
    fake_urlopen.return_value = _json_response({"projects": []})

    result = vercel.find_project_by_repo("tok", "lauriand/portfolio")
    assert result is None


def test_create_project_posts_payload_and_returns_id(fake_urlopen):
    fake_urlopen.return_value = _json_response({"id": "prj_xyz", "name": "portfolio"})

    result = vercel.create_project(
        token="tok",
        name="portfolio",
        github_repo="lauriand/portfolio",
    )
    assert result == "prj_xyz"


def test_set_env_var_creates_preview_scoped(fake_urlopen):
    # First call: list env vars (empty), second call: create env var
    fake_urlopen.side_effect = [
        _json_response({"envs": []}),
        _json_response({"id": "env_1"}),
    ]

    vercel.set_env_var(
        token="tok",
        project_id="prj_xyz",
        key="CMS_PREVIEW_TOKEN",
        value="secret",
        target=["preview"],
    )

    # Verify the 2nd request body (the POST /env call)
    call = fake_urlopen.call_args_list[1][0][0]
    body = json.loads(call.data.decode())
    assert body["key"] == "CMS_PREVIEW_TOKEN"
    assert body["value"] == "secret"
    assert body["target"] == ["preview"]


def test_trigger_deployment_from_branch(fake_urlopen):
    fake_urlopen.return_value = _json_response({
        "id": "dpl_1",
        "url": "portfolio-git-cms-preview.vercel.app",
    })

    result = vercel.trigger_deployment(
        token="tok",
        project_id="prj_xyz",
        github_repo="lauriand/portfolio",
        branch="cms-preview",
        production_branch="master",
    )
    assert result["url"] == "portfolio-git-cms-preview.vercel.app"


def test_trigger_deployment_targets_production_on_prod_branch(fake_urlopen):
    fake_urlopen.return_value = _json_response({"id": "dpl_p", "url": "portfolio.vercel.app"})

    vercel.trigger_deployment(
        token="tok",
        project_id="prj_xyz",
        github_repo="lauriand/portfolio",
        branch="master",
        production_branch="master",
    )

    call = fake_urlopen.call_args_list[0][0][0]
    body = json.loads(call.data.decode())
    assert body["target"] == "production"


def test_trigger_deployment_targets_preview_on_non_prod_branch(fake_urlopen):
    fake_urlopen.return_value = _json_response({"id": "dpl_q", "url": "p-git-x.vercel.app"})

    vercel.trigger_deployment(
        token="tok",
        project_id="prj_xyz",
        github_repo="lauriand/portfolio",
        branch="cms-preview",
        production_branch="master",
    )

    call = fake_urlopen.call_args_list[0][0][0]
    body = json.loads(call.data.decode())
    assert body["target"] is None
