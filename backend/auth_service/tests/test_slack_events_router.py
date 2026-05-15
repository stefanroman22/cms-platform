"""Integration tests for POST /slack/events."""

from __future__ import annotations

import hashlib
import hmac
import json
import time


def _sign(body: bytes, ts: str, secret: str) -> str:
    base = f"v0:{ts}:{body.decode()}".encode()
    return "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()


def test_url_verification_returns_challenge(client, monkeypatch):
    from auth_service.core import config

    monkeypatch.setattr(config.settings, "SLACK_SIGNING_SECRET", "secret")

    payload = {"type": "url_verification", "challenge": "abc123"}
    body = json.dumps(payload).encode()

    resp = client.post("/slack/events", content=body, headers={"content-type": "application/json"})
    assert resp.status_code == 200
    assert resp.text == "abc123"


def test_bad_signature_returns_401(client, monkeypatch):
    from auth_service.core import config

    monkeypatch.setattr(config.settings, "SLACK_SIGNING_SECRET", "secret")

    payload = {"type": "event_callback", "event": {"type": "reaction_added"}, "event_id": "Ev1"}
    body = json.dumps(payload).encode()
    ts = str(int(time.time()))

    resp = client.post(
        "/slack/events",
        content=body,
        headers={
            "content-type": "application/json",
            "x-slack-request-timestamp": ts,
            "x-slack-signature": "v0=deadbeef",
        },
    )
    assert resp.status_code == 401


def test_reaction_event_dispatched(client, monkeypatch):
    from auth_service.core import config

    monkeypatch.setattr(config.settings, "SLACK_SIGNING_SECRET", "secret")
    monkeypatch.setattr(
        "auth_service.routers.slack_events.slack_events_dedup.already_processed",
        lambda eid: False,
    )
    monkeypatch.setattr(
        "auth_service.routers.slack_events.slack_events_dedup.mark_processed",
        lambda eid: None,
    )

    payload = {
        "type": "event_callback",
        "event_id": "Ev_REACT_1",
        "event": {"type": "reaction_added", "reaction": "white_check_mark"},
    }
    body = json.dumps(payload).encode()
    ts = str(int(time.time()))
    sig = _sign(body, ts, "secret")

    called: list[dict] = []
    monkeypatch.setattr(
        "auth_service.routers.slack_events.slack_handler.handle_reaction_added",
        lambda event: called.append(event),
    )

    resp = client.post(
        "/slack/events",
        content=body,
        headers={
            "content-type": "application/json",
            "x-slack-request-timestamp": ts,
            "x-slack-signature": sig,
        },
    )
    assert resp.status_code == 200
    assert len(called) == 1
    assert called[0]["type"] == "reaction_added"


def test_message_event_dispatched(client, monkeypatch):
    from auth_service.core import config

    monkeypatch.setattr(config.settings, "SLACK_SIGNING_SECRET", "secret")
    monkeypatch.setattr(
        "auth_service.routers.slack_events.slack_events_dedup.already_processed",
        lambda eid: False,
    )
    monkeypatch.setattr(
        "auth_service.routers.slack_events.slack_events_dedup.mark_processed",
        lambda eid: None,
    )

    payload = {
        "type": "event_callback",
        "event_id": "Ev_MSG_1",
        "event": {"type": "message", "text": "hi"},
    }
    body = json.dumps(payload).encode()
    ts = str(int(time.time()))
    sig = _sign(body, ts, "secret")

    called: list[dict] = []
    monkeypatch.setattr(
        "auth_service.routers.slack_events.slack_handler.handle_message",
        lambda event: called.append(event),
    )

    resp = client.post(
        "/slack/events",
        content=body,
        headers={
            "content-type": "application/json",
            "x-slack-request-timestamp": ts,
            "x-slack-signature": sig,
        },
    )
    assert resp.status_code == 200
    assert len(called) == 1


def test_duplicate_event_id_short_circuits(client, monkeypatch):
    from auth_service.core import config

    monkeypatch.setattr(config.settings, "SLACK_SIGNING_SECRET", "secret")
    monkeypatch.setattr(
        "auth_service.routers.slack_events.slack_events_dedup.already_processed",
        lambda eid: True,
    )

    payload = {
        "type": "event_callback",
        "event_id": "Ev_DUP",
        "event": {"type": "reaction_added"},
    }
    body = json.dumps(payload).encode()
    ts = str(int(time.time()))
    sig = _sign(body, ts, "secret")

    called: list[dict] = []
    monkeypatch.setattr(
        "auth_service.routers.slack_events.slack_handler.handle_reaction_added",
        lambda event: called.append(event),
    )

    resp = client.post(
        "/slack/events",
        content=body,
        headers={
            "content-type": "application/json",
            "x-slack-request-timestamp": ts,
            "x-slack-signature": sig,
        },
    )
    assert resp.status_code == 200
    assert called == []


def test_unknown_event_type_returns_200(client, monkeypatch):
    from auth_service.core import config

    monkeypatch.setattr(config.settings, "SLACK_SIGNING_SECRET", "secret")
    monkeypatch.setattr(
        "auth_service.routers.slack_events.slack_events_dedup.already_processed",
        lambda eid: False,
    )
    monkeypatch.setattr(
        "auth_service.routers.slack_events.slack_events_dedup.mark_processed",
        lambda eid: None,
    )

    payload = {
        "type": "event_callback",
        "event_id": "Ev_UNK",
        "event": {"type": "team_join"},
    }
    body = json.dumps(payload).encode()
    ts = str(int(time.time()))
    sig = _sign(body, ts, "secret")

    resp = client.post(
        "/slack/events",
        content=body,
        headers={
            "content-type": "application/json",
            "x-slack-request-timestamp": ts,
            "x-slack-signature": sig,
        },
    )
    assert resp.status_code == 200
