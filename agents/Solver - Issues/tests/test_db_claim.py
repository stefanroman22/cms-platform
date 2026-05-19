"""Atomic claim SQL behavior tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import db
import pytest


@pytest.fixture
def mock_pg(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://localhost")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "key")
    monkeypatch.setenv("SOLVER_MAX_RETRIES", "3")
    monkeypatch.setenv("SOLVER_STALE_CLAIM_MINUTES", "15")

    captured = {"calls": [], "next_result": []}

    fake_sb = MagicMock()
    fake_rpc_chain = MagicMock()

    def fake_rpc(fn_name, params):
        captured["calls"].append({"fn": fn_name, "params": params})
        return fake_rpc_chain

    fake_sb.rpc.side_effect = fake_rpc
    fake_rpc_chain.execute = lambda: MagicMock(data=captured["next_result"])

    monkeypatch.setattr(db, "_supabase", lambda: fake_sb)
    return captured


def test_claim_returns_none_when_queue_empty(mock_pg):
    mock_pg["next_result"] = []
    assert db.claim_next_issue() is None


def test_claim_returns_first_row_when_present(mock_pg):
    row = {
        "id": "issue-1",
        "project_id": "proj-1",
        "title": "x",
        "description": "y",
        "priority": "High",
        "status": "pending",
        "revision_feedback": None,
    }
    mock_pg["next_result"] = [row]
    assert db.claim_next_issue() == row


def test_claim_uses_correct_rpc_name(mock_pg):
    mock_pg["next_result"] = []
    db.claim_next_issue()
    assert mock_pg["calls"][0]["fn"] == "claim_next_solver_issue"


def test_claim_passes_env_overrides_to_rpc(monkeypatch, mock_pg):
    monkeypatch.setenv("SOLVER_MAX_RETRIES", "5")
    monkeypatch.setenv("SOLVER_STALE_CLAIM_MINUTES", "30")
    mock_pg["next_result"] = []
    db.claim_next_issue()
    params = mock_pg["calls"][0]["params"]
    assert params["p_max_retries"] == 5
    assert params["p_stale_minutes"] == 30


def test_claim_specific_returns_row_when_eligible(mock_pg):
    row = {
        "id": "issue-77",
        "project_id": "proj-1",
        "title": "x",
        "description": "y",
        "priority": "High",
        "status": "pending",
        "revision_feedback": None,
    }
    mock_pg["next_result"] = [row]
    assert db.claim_specific_issue("issue-77") == row


def test_claim_specific_returns_none_when_ineligible(mock_pg):
    mock_pg["next_result"] = []
    assert db.claim_specific_issue("issue-77") is None


def test_claim_specific_uses_correct_rpc_name(mock_pg):
    mock_pg["next_result"] = []
    db.claim_specific_issue("issue-77")
    assert mock_pg["calls"][0]["fn"] == "claim_specific_solver_issue"


def test_claim_specific_passes_issue_id_param(mock_pg):
    mock_pg["next_result"] = []
    db.claim_specific_issue("issue-abc")
    assert mock_pg["calls"][0]["params"]["p_issue_id"] == "issue-abc"


def test_claim_specific_respects_env_overrides(monkeypatch, mock_pg):
    monkeypatch.setenv("SOLVER_MAX_RETRIES", "5")
    monkeypatch.setenv("SOLVER_STALE_CLAIM_MINUTES", "30")
    mock_pg["next_result"] = []
    db.claim_specific_issue("issue-x")
    assert mock_pg["calls"][0]["params"]["p_max_retries"] == 5
    assert mock_pg["calls"][0]["params"]["p_stale_minutes"] == 30
