"""Browser draft namespaces must follow the authenticated actor, never headers alone."""

import pytest
from fastapi.testclient import TestClient

from backend.application import app


def test_local_draft_namespace_is_stable_and_noncredential() -> None:
    with TestClient(app, base_url="http://localhost") as client:
        first = client.get("/api/session").json()["draft_scope"]
        assert client.get("/api/session").json()["draft_scope"] == first
        assert len(first) == 64
        assert client.get("/api/session").headers["Cache-Control"] == "no-store"
        assert client.get("/api/session", headers={"X-Circuit-Actor": "other"}).json()["draft_scope"] == first


def test_hosted_draft_namespace_is_identity_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CIRCUIT_PUBLIC_URL", "https://circuit-lab.christopherrehm.de")
    monkeypatch.setenv("CIRCUIT_PROXY_TOKEN", "a-private-proxy-secret-of-at-least-32-characters")
    headers = {"X-Circuit-Proxy-Token": "a-private-proxy-secret-of-at-least-32-characters", "X-Circuit-Actor": "person-one"}
    with TestClient(app, base_url="http://localhost") as client:
        first = client.get("/api/session", headers=headers).json()["draft_scope"]
        second = client.get("/api/session", headers={**headers, "X-Circuit-Actor": "person-two"}).json()["draft_scope"]
        assert first != second
        assert client.get("/api/session", headers={"X-Circuit-Actor": "person-one"}).status_code == 403
