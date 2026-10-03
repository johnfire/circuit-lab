"""Hosted boundary tests: proxy identity, origin checks, and safe local defaults."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.application import app
from backend.request_security import allowed_hosts, public_url

PUBLIC_URL = "https://circuit-lab.christopherrehm.de"
TEST_PROXY_TOKEN = "test-only-proxy-token-not-a-production-secret"


@pytest.fixture
def hosted_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("CIRCUIT_PUBLIC_URL", PUBLIC_URL)
    monkeypatch.setenv("CIRCUIT_PROXY_TOKEN", TEST_PROXY_TOKEN)
    monkeypatch.setenv("CIRCUIT_AUDIT_PATH", str(tmp_path / "hosted-audit.jsonl"))
    return TestClient(app, base_url="http://localhost")


def proxy_headers(actor: str = "chris") -> dict[str, str]:
    return {"X-Circuit-Proxy-Token": TEST_PROXY_TOKEN, "X-Circuit-Actor": actor,
            "Origin": PUBLIC_URL}


def test_hosted_mode_rejects_direct_access_and_forged_identity(hosted_client: TestClient) -> None:
    assert hosted_client.get("/api/circuits").status_code == 403
    assert hosted_client.get("/api/circuits", headers={"X-Circuit-Actor": "chris"}).status_code == 403
    assert hosted_client.get("/api/circuits", headers={
        "X-Circuit-Proxy-Token": TEST_PROXY_TOKEN,
    }).status_code == 401


def test_authenticated_job_is_attributed_to_the_real_actor(
    hosted_client: TestClient, tmp_path: Path,
) -> None:
    response = hosted_client.post("/api/circuits/voltage_divider/simulate",
                                  json={}, headers=proxy_headers())
    assert response.status_code == 200
    events = [json.loads(line) for line in (tmp_path / "hosted-audit.jsonl").read_text().splitlines()]
    assert all(event["actor"] == "user:chris" for event in events)


def test_ai_verification_is_not_attributed_to_a_human(
    hosted_client: TestClient, tmp_path: Path,
) -> None:
    response = hosted_client.post("/api/circuits/voltage_divider/simulate",
                                  json={}, headers=proxy_headers("ai-agent:deployment-verifier"))
    assert response.status_code == 200
    events = [json.loads(line) for line in (tmp_path / "hosted-audit.jsonl").read_text().splitlines()]
    assert all(event["actor"] == "ai-agent:deployment-verifier" for event in events)


@pytest.mark.parametrize("origin", [
    "https://evil.example", "https://circuit-lab.christopherrehm.de.evil.example",
    "http://circuit-lab.christopherrehm.de", "null", "http://localhost",
])
def test_hosted_mode_rejects_foreign_origins(hosted_client: TestClient, origin: str) -> None:
    headers = {**proxy_headers(), "Origin": origin}
    assert hosted_client.post("/api/circuits/voltage_divider/simulate",
                              json={}, headers=headers).status_code == 403


def test_missing_proxy_secret_fails_closed(
    hosted_client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CIRCUIT_PROXY_TOKEN")
    assert hosted_client.get("/api/circuits", headers=proxy_headers()).status_code == 403
    assert hosted_client.get("/api/health").status_code == 200


@pytest.mark.parametrize("url", [
    "http://example.com", "https://example.com/path", "https://user@example.com",
    "https://example.com?secret=x", "https://example.com#fragment",
])
def test_invalid_hosted_origins_are_rejected(url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CIRCUIT_PUBLIC_URL", url)
    with pytest.raises(ValueError):
        public_url()


def test_exact_public_hostname_is_added_to_trusted_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CIRCUIT_PUBLIC_URL", PUBLIC_URL)
    assert "circuit-lab.christopherrehm.de" in allowed_hosts()


def test_public_demo_requires_trusted_proxy_even_without_login(
    hosted_client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CIRCUIT_ACCESS_MODE", "public")
    assert hosted_client.get("/api/circuits").status_code == 403
    headers = {"X-Circuit-Proxy-Token": TEST_PROXY_TOKEN}
    assert hosted_client.get("/api/circuits", headers=headers).status_code == 200
