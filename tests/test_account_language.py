"""Language updates stay bound to the signed-in subject and preserve the rest of the profile."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import account_language
from backend.account_language import profile_with_language
from backend.application import app


def test_locale_update_preserves_profile_and_attributes():
    profile = {"id": "owner", "username": "person", "firstName": "First", "lastName": "Last",
               "email": "person@example.invalid", "attributes": {"custom": ["kept"], "locale": ["en"]},
               "userProfileMetadata": {"server": "only"}}
    updated = profile_with_language(profile, "de")
    assert updated == {"username": "person", "firstName": "First", "lastName": "Last",
                       "email": "person@example.invalid", "attributes": {"custom": ["kept"], "locale": ["de"]}}
    assert profile["attributes"]["locale"] == ["en"]


def test_own_locale_update_is_idempotent_and_audited(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    profile = {"id": "owner", "firstName": "First", "lastName": "Last", "attributes": {"locale": ["en"]}}
    writes = []

    def identity_request(token, updated=None):
        if updated is not None:
            writes.append(updated)
            profile.update(updated)
            return {}
        return dict(profile)

    audit = tmp_path / "actions.jsonl"
    monkeypatch.setenv("CIRCUIT_AUDIT_PATH", str(audit))
    monkeypatch.setattr(account_language, "own_profile", lambda request: {"sub": "owner"})
    monkeypatch.setattr(account_language, "account_request", identity_request)
    with TestClient(app, base_url="http://localhost") as client:
        for _ in range(2):
            response = client.post("/api/account/language", json={"language": "de"})
            assert response.status_code == 200 and response.json() == {"language": "de"}
        assert client.post("/api/account/language", json={"language": "ar"}).status_code == 422
    assert len(writes) == 1
    events = [json.loads(line) for line in audit.read_text().splitlines()]
    assert [event["outcome"] for event in events] == ["started", "completed"]
    assert {event["action"] for event in events} == {"account.language"}
    assert {event["actor"] for event in events} == {"user:local"}


def test_mismatched_subject_never_writes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("CIRCUIT_AUDIT_PATH", str(tmp_path / "audit.jsonl"))
    monkeypatch.setattr(account_language, "own_profile", lambda request: {"sub": "owner"})
    writes = []
    monkeypatch.setattr(account_language, "account_request", lambda token, profile=None:
                        writes.append(profile) if profile else {"id": "other-owner"})
    with TestClient(app, base_url="http://localhost") as client:
        assert client.post("/api/account/language", json={"language": "de"}).status_code == 503
    assert not writes
