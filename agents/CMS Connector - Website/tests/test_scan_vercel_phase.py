from unittest.mock import patch

import scan


def test_vercel_setup_creates_project_and_provisions_token_via_rotate():
    manifest = {"project_slug": "demo"}

    def fake_http(method, url, headers, body=None):
        if method == "GET":
            return None  # no existing project row
        if url.endswith("/rotate-preview-token"):
            return {"preview_token": "tok32"}  # backend mints + persists (DB + Vercel)
        return {"updated": 5}

    with (
        patch.object(scan, "vercel") as mock_vercel,
        patch.object(scan, "github") as mock_gh,
        patch.object(scan, "_http", side_effect=fake_http) as mock_http,
    ):
        mock_vercel.find_project_by_repo.return_value = None  # project doesn't exist yet
        mock_vercel.create_project.return_value = "prj_abc"
        mock_gh.get_default_branch.return_value = "main"
        mock_vercel.trigger_deployment.side_effect = [
            {"id": "dpl_1", "url": "portfolio.vercel.app"},  # prod
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
        mock_vercel.disable_deployment_protection.assert_called_once_with("vtok", "prj_abc")
        mock_gh.ensure_branch_unprotected.assert_called_once_with(
            "gtok", "lauriand/portfolio", "main"
        )
        mock_gh.create_branch.assert_called_once_with(
            "gtok", "lauriand/portfolio", "cms-preview", from_branch="main"
        )

        # Env vars: 2 × CMS_ENDPOINT (prod + preview), 1 × CMS_PREVIEW_TOKEN (preview)
        assert mock_vercel.set_env_var.call_count == 3
        # The token is set under the SERVER-ONLY key (never NEXT_PUBLIC_) on preview.
        token_calls = [
            c for c in mock_vercel.set_env_var.call_args_list if c[0][2] == "CMS_PREVIEW_TOKEN"
        ]
        assert len(token_calls) == 1
        assert token_calls[0][0][3] == "tok32"
        assert token_calls[0][1].get("target") == ["preview"]
        # No NEXT_PUBLIC_ token key is ever set (would leak the credential to the client bundle).
        assert not any(
            "PREVIEW_TOKEN" in c[0][2] and c[0][2] != "CMS_PREVIEW_TOKEN"
            for c in mock_vercel.set_env_var.call_args_list
        )

        # The token is provisioned via the rotate endpoint (single DB+Vercel writer).
        assert any(
            c[0][0] == "POST" and c[0][1].endswith("/rotate-preview-token")
            for c in mock_http.call_args_list
        )

        # PATCH saves Vercel metadata — but NOT preview_token (AdminProjectPatchIn drops it).
        patch_calls = [c for c in mock_http.call_args_list if c[0][0] == "PATCH"]
        assert len(patch_calls) == 1
        patched_body = patch_calls[0][0][3]
        assert patched_body.get("vercel_project_id") == "prj_abc"
        assert patched_body.get("production_url") == "https://portfolio.vercel.app"
        assert patched_body.get("preview_url") == "https://portfolio-git-cms-preview.vercel.app"
        assert "preview_token" not in patched_body


def test_vercel_setup_reuses_existing_token_and_does_not_rotate_on_rerun():
    """Idempotency: re-running against a project that already has a token must NOT
    rotate (which would mint a new one); it mirrors the existing token onto Vercel."""
    manifest = {"project_slug": "demo"}

    existing_project = {
        "github_repo": "lauriand/portfolio",
        "vercel_project_id": "prj_existing",
        "preview_token": "ORIGINAL_TOKEN",
        "production_url": "https://portfolio.vercel.app",
        "preview_url": "https://portfolio-git-cms-preview.vercel.app",
    }

    def fake_http(method, url, headers, body=None):
        if method == "GET":
            return existing_project
        if url.endswith("/rotate-preview-token"):
            return {"preview_token": "NEWTOK_SHOULD_NOT_BE_USED"}
        return {"updated": 5}

    with (
        patch.object(scan, "vercel") as mock_vercel,
        patch.object(scan, "github") as mock_gh,
        patch.object(scan, "_http", side_effect=fake_http) as mock_http,
    ):
        mock_vercel.find_project_by_repo.return_value = {
            "id": "prj_existing",
            "production_branch": "master",
        }
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

        mock_vercel.create_project.assert_not_called()
        mock_vercel.disable_deployment_protection.assert_called_once_with("vtok", "prj_existing")
        mock_gh.ensure_branch_unprotected.assert_called_once_with(
            "gtok", "lauriand/portfolio", "master"
        )
        mock_gh.create_branch.assert_not_called()

        # Idempotency: an existing DB token must NOT trigger a rotate (no new token).
        assert not any(
            c[0][0] == "POST" and c[0][1].endswith("/rotate-preview-token")
            for c in mock_http.call_args_list
        )
        # The existing token is mirrored onto Vercel under the server-only key.
        token_calls = [
            c for c in mock_vercel.set_env_var.call_args_list if c[0][2] == "CMS_PREVIEW_TOKEN"
        ]
        assert len(token_calls) == 1
        assert token_calls[0][0][3] == "ORIGINAL_TOKEN"

        # PATCH never carries preview_token.
        patch_calls = [c for c in mock_http.call_args_list if c[0][0] == "PATCH"]
        assert len(patch_calls) == 1
        assert "preview_token" not in patch_calls[0][0][3]
