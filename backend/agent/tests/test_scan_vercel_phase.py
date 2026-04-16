import json
from unittest.mock import MagicMock, patch

import pytest

from .. import scan


def test_vercel_setup_creates_project_and_saves_urls_to_cms():
    manifest = {"project_slug": "demo"}

    with patch.object(scan, "vercel") as mock_vercel, \
         patch.object(scan, "github") as mock_gh, \
         patch.object(scan, "_http") as mock_http, \
         patch("secrets.token_urlsafe", return_value="tok32"):

        # _http GET returns None → no existing project row
        mock_http.side_effect = lambda method, url, headers, body=None: (
            None if method == "GET" else {"updated": 5}
        )

        mock_vercel.find_project_by_repo.return_value = None  # project doesn't exist yet
        mock_vercel.create_project.return_value = "prj_abc"
        mock_vercel.trigger_deployment.side_effect = [
            {"id": "dpl_1", "url": "portfolio.vercel.app"},         # prod
            {"id": "dpl_2", "url": "portfolio-git-cms-preview.vercel.app"},  # preview
        ]
        mock_gh.branch_exists.return_value = False

        scan._vercel_setup(
            manifest=manifest,
            github_repo="lauriand/portfolio",
            vercel_token="vtok",
            github_token="gtok",
            cms_api_url="http://localhost:8001",
            cms_api_token="ctok",
            cms_endpoint_base="https://cms.example.com",
        )

        mock_vercel.create_project.assert_called_once()
        mock_gh.create_branch.assert_called_once_with("gtok", "lauriand/portfolio", "cms-preview", from_branch="main")

        # Env vars set: prod + preview (2 × CMS_ENDPOINT, 1 × CMS_PREVIEW_TOKEN)
        assert mock_vercel.set_env_var.call_count == 3

        # PATCH to CMS to save vercel_project_id, production_url, preview_url, preview_token
        patch_calls = [c for c in mock_http.call_args_list if c[0][0] == "PATCH"]
        assert len(patch_calls) == 1
        patched_body = patch_calls[0][0][3]
        assert patched_body.get("vercel_project_id") == "prj_abc"
        assert patched_body.get("production_url") == "https://portfolio.vercel.app"
        assert patched_body.get("preview_url") == "https://portfolio-git-cms-preview.vercel.app"
        assert patched_body.get("preview_token") == "tok32"


def test_vercel_setup_preserves_existing_preview_token_on_rerun():
    """Idempotency: re-running against an existing project must not regenerate the token."""
    manifest = {"project_slug": "demo"}

    with patch.object(scan, "vercel") as mock_vercel, \
         patch.object(scan, "github") as mock_gh, \
         patch.object(scan, "_http") as mock_http, \
         patch("secrets.token_urlsafe", return_value="newtok_should_not_be_used"):

        # _http GET returns existing project with existing preview_token
        existing_project = {
            "github_repo": "lauriand/portfolio",
            "vercel_project_id": "prj_existing",
            "preview_token": "ORIGINAL_TOKEN",
            "production_url": "https://portfolio.vercel.app",
            "preview_url": "https://portfolio-git-cms-preview.vercel.app",
        }
        mock_http.side_effect = lambda method, url, headers, body=None: (
            existing_project if method == "GET" else {"updated": 5}
        )

        mock_vercel.find_project_by_repo.return_value = "prj_existing"
        mock_vercel.trigger_deployment.side_effect = [
            {"id": "dpl_1", "url": "portfolio.vercel.app"},
            {"id": "dpl_2", "url": "portfolio-git-cms-preview.vercel.app"},
        ]
        mock_gh.branch_exists.return_value = True

        scan._vercel_setup(
            manifest=manifest,
            github_repo="lauriand/portfolio",
            vercel_token="vtok",
            github_token="gtok",
            cms_api_url="http://localhost:8001",
            cms_api_token="ctok",
            cms_endpoint_base="https://cms.example.com",
        )

        # Idempotency: no creation of project or branch
        mock_vercel.create_project.assert_not_called()
        mock_gh.create_branch.assert_not_called()

        # PATCH was called; must have reused ORIGINAL_TOKEN, not the fresh one
        patch_calls = [c for c in mock_http.call_args_list if c[0][0] == "PATCH"]
        assert len(patch_calls) == 1
        patched_body = patch_calls[0][0][3]
        assert patched_body.get("preview_token") == "ORIGINAL_TOKEN"
