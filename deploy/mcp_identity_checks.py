"""Real isolated Keycloak introspection, scoped client identity and password lifecycle checks."""

import asyncio
import json
import secrets
import time
import urllib.parse
from typing import cast

from backend.project_identity import KeycloakVerifier
from deploy.identity_checks import IDENTITY, PUBLIC, admin_headers, request
from deploy.mcp_identity_configuration import oauth_additions

BASE = IDENTITY + "/auth/admin/realms/circuit-lab"
RESOURCE_SECRET = "isolated-test-resource-not-production"


def admin_create(path: str, payload: object, headers: dict[str, str]) -> str:
    """This helper's request function permits only the local test identity service."""
    status, response, _ = request(BASE + path, json.dumps(payload).encode(), headers)
    assert status == 201, "Cannot create isolated identity fixture: " + path
    return response["Location"].rsplit("/", 1)[1]


def configure_fixture(headers: dict[str, str], client: str) -> tuple[str, str]:
    """The test token mint uses a synthetic password grant; production clients remain PKCE-only."""
    configured = oauth_additions(PUBLIC, "http://127.0.0.1:8124/callback", client)
    scopes = cast(list[dict[str, object]], configured["clientScopes"])
    for scope in scopes:
        status, _, _ = request(BASE + "/client-scopes", json.dumps(scope).encode(), headers)
        assert status in {201, 409}, "Cannot configure fixture scopes"
    public, resource = cast(list[dict[str, object]], configured["clients"])
    public["directAccessGrantsEnabled"] = True
    public["consentRequired"] = False
    resource["secret"] = RESOURCE_SECRET
    status, _, body = request(BASE + "/clients?clientId=circuit-lab-mcp-resource", headers=headers)
    assert status == 200
    existing = json.loads(body)
    resource_id = existing[0]["id"] if existing else admin_create("/clients", resource, headers)
    client_id = admin_create("/clients", public, headers)
    status, _, body = request(BASE + "/clients/" + resource_id + "/service-account-user", headers=headers)
    assert status == 200
    service_account = json.loads(body)["id"]
    status, _, body = request(BASE + "/clients?clientId=realm-management", headers=headers)
    assert status == 200
    management = json.loads(body)[0]["id"]
    roles = []
    for name in ("view-users", "view-events"):
        status, _, body = request(BASE + "/clients/" + management + "/roles/" + name, headers=headers)
        assert status == 200
        roles.append(json.loads(body))
    status, _, _ = request(BASE + "/users/" + service_account + "/role-mappings/clients/" + management,
                          json.dumps(roles).encode(), headers)
    assert status == 204
    status, _, _ = request(BASE + "/clients/" + resource_id + "/scope-mappings/clients/" + management,
                          json.dumps(roles).encode(), headers)
    assert status == 204
    return resource_id, client_id


def mint_token(client: str, email: str, password: str) -> str:
    """Create a real short-lived token from this synthetic local-only account."""
    form = urllib.parse.urlencode({"client_id": client, "grant_type": "password", "username": email,
                                  "password": password, "scope": "openid email circuit:read circuit:edit circuit:simulate circuit:view"})
    status, _, body = request(IDENTITY + "/auth/realms/circuit-lab/protocol/openid-connect/token", form.encode(),
                             {"Content-Type": "application/x-www-form-urlencoded", "X-Forwarded-Proto": "https"})
    assert status == 200, "Real test token could not be issued"
    return str(json.loads(body)["access_token"])


async def verify_real_identity(client: str, owner: str, token: str, headers: dict[str, str]) -> None:
    """Active token verification and admin password-event visibility use dedicated read-only roles."""
    verifier = KeycloakVerifier(PUBLIC + "/auth/realms/circuit-lab", IDENTITY + "/auth/realms/circuit-lab",
                               PUBLIC + "/mcp", "circuit-lab-mcp-resource", RESOURCE_SECRET, frozenset({client}))
    checked = await verifier.verify_token(token)
    assert checked is not None and checked.subject == owner and checked.client_id == client, {
        key: value for key, value in (await verifier.introspect(token) or {}).items()
        if key in {"active", "iss", "aud", "scope", "email_verified", "iat", "exp", "client_id", "sub"}}
    assert {"circuit:read", "circuit:edit", "circuit:simulate", "circuit:view"} <= set(checked.scopes)
    await asyncio.to_thread(verify_http_bearer, verifier, token)
    wrong = KeycloakVerifier(verifier.issuer, verifier.internal_base, PUBLIC + "/another-resource",
                             verifier.client_id, verifier.secret, verifier.approved_clients)
    assert await wrong.verify_token(token) is None
    status, _, _ = request(BASE + "/users/" + owner + "/reset-password", json.dumps({"type": "password",
        "value": secrets.token_urlsafe(24), "temporary": False}).encode(), headers, method="PUT")
    assert status == 204
    await verify_lifecycle_visibility(verifier, owner)
    status, _, _ = request(BASE + "/users/" + owner + "/logout", b"", headers)
    assert status == 204
    assert await verifier.verify_token(token) is None


def verify_http_bearer(verifier: KeycloakVerifier, token: str) -> None:
    """The mounted SDK accepts a genuine bearer and rejects a forged actor without one."""
    from fastapi.testclient import TestClient

    from backend.application import app, collaboration
    previous = collaboration.verifier
    collaboration.verifier = verifier
    try:
        with TestClient(app, base_url="http://localhost") as client:
            message = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "verified-http", "version": "1"}}}
            headers = {"Accept": "application/json, text/event-stream", "Authorization": "Bearer " + token}
            accepted = client.post("/mcp", json=message, headers=headers)
            assert accepted.status_code == 200 and "serverInfo" in accepted.json()["result"]
            refused = client.post("/mcp", json=message, headers={"Accept": headers["Accept"], "X-Circuit-Actor": "forged-owner"})
            assert refused.status_code == 401 and "resource_metadata" in refused.headers["www-authenticate"]
    finally:
        collaboration.verifier = previous


async def verify_lifecycle_visibility(verifier: KeycloakVerifier, owner: str) -> None:
    """Fail if least-privilege credentials cannot see the actual admin password event."""
    from backend.project_identity import identity_payload, identity_request
    credentials = {"grant_type": "client_credentials", "client_id": verifier.client_id, "client_secret": verifier.secret}
    issued = await asyncio.to_thread(identity_request, verifier.internal_base + "/protocol/openid-connect/token", credentials)
    bearer = str(issued["access_token"])
    admin_base = verifier.internal_base.replace("/realms/circuit-lab", "/admin/realms/circuit-lab")
    configuration = await asyncio.to_thread(identity_request, admin_base + "/events/config", {}, bearer)
    assert configuration["eventsEnabled"] and configuration["adminEventsEnabled"] and not configuration["adminEventsDetailsEnabled"]
    user = await asyncio.to_thread(identity_request, admin_base + "/users/" + owner, {}, bearer)
    assert user["id"] == owner
    query = urllib.parse.urlencode({"resourcePath": f"users/{owner}/reset-password", "max": "1"})
    events = await asyncio.to_thread(identity_payload, admin_base + "/admin-events?" + query, {}, bearer)
    assert isinstance(events, list) and events and int(events[0]["time"]) > (time.time() - 30) * 1000


def main() -> None:
    """Synthetic accounts on hard-coded loopback only; no production realm or secrets are accessed."""
    headers = admin_headers()
    client = "mcp-check-" + secrets.token_hex(6)
    configure_fixture(headers, client)
    email, password = client + "@example.invalid", secrets.token_urlsafe(24)
    owner = admin_create("/users", {"username": email, "email": email, "emailVerified": True, "enabled": True,
        "firstName": "MCP", "lastName": "Fixture", "credentials": [{"type": "password", "value": password, "temporary": False}]}, headers)
    token = mint_token(client, email, password)
    asyncio.run(verify_real_identity(client, owner, token, headers))
    print("Real Keycloak resource audience, scoped introspection, read-only lifecycle roles and logout rejection passed")


if __name__ == "__main__":
    main()
