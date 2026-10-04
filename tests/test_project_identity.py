"""Bearers must be active, verified, resource-bound and from an approved OAuth client."""

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.application import app
from backend.project_identity import KeycloakVerifier, valid_identity_claims


def identity_claims():
    return {"active": True, "iss": "https://example.test/auth/realms/circuit-lab", "sub": "verified-user",
            "email_verified": True, "iat": int(time.time()), "exp": int(time.time()) + 60,
            "client_id": "codex-test", "scope": "circuit:read circuit:edit", "aud": "https://example.test/mcp"}


@pytest.mark.parametrize("changed", [{"active": False}, {"iss": "https://attacker.test"},
    {"email_verified": False}, {"exp": 0}, {"iat": "1"}, {"iat": True}, {"iat": -1}, {"sub": "forged/owner"}])
def test_identity_claim_validation_rejects_untrusted_claims(changed):
    assert not valid_identity_claims({**identity_claims(), **changed}, identity_claims()["iss"])


@pytest.mark.parametrize("changed", [{"aud": "https://other.test/mcp"}, {"client_id": "unreviewed-client"},
                                       {"scope": "circuit:edit"}, {"aud": []}])
def test_bearers_cannot_substitute_resource_client_or_read_scope(changed):
    verifier = KeycloakVerifier(identity_claims()["iss"], identity_claims()["iss"], "https://example.test/mcp",
                                "resource", "test-only", frozenset({"codex-test"}))
    with patch.object(KeycloakVerifier, "introspect", AsyncMock(return_value={**identity_claims(), **changed})):
        assert asyncio.run(verifier.verify_token("test-only-token")) is None


def test_mcp_http_requires_own_bearer_boundary_and_public_metadata():
    with TestClient(app, base_url="http://localhost") as client:
        metadata = client.get("/.well-known/oauth-protected-resource/mcp")
        assert metadata.status_code == 200
        assert metadata.json()["resource"].endswith("/mcp")
        response = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}},
            headers={"Accept": "application/json, text/event-stream", "X-Circuit-Actor": "verified-user"})
        assert response.status_code == 401
        assert "resource_metadata" in response.headers["www-authenticate"]
