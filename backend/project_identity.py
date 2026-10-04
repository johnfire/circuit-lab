"""Keycloak introspection: verified bearer identity, audience, expiry and client binding."""

import asyncio
import json
import logging
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import cast
from uuid import uuid4

from fastapi import Request
from mcp.server.auth.provider import AccessToken

from backend.project_database import decode_record
from backend.project_models import Principal, ProjectFailure
from backend.request_security import public_url

LOGGER = logging.getLogger("circuit-lab.identity")
PERMISSIONS = frozenset({"read", "edit", "simulate", "view"})


def identity_request(endpoint: str, submitted: dict[str, str], bearer: str | None = None) -> dict[str, object]:
    """Read only configured identity URLs with bounded time, response and no redirects."""
    return decode_record(identity_payload(endpoint, submitted, bearer))


def identity_payload(endpoint: str, submitted: dict[str, str], bearer: str | None = None) -> object:
    """Permit bounded identity arrays for lifecycle reconciliation, never arbitrary URLs."""
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if bearer:
        headers["Authorization"] = "Bearer " + bearer
    body = urllib.parse.urlencode(submitted).encode() if submitted else None
    request = urllib.request.Request(endpoint, data=body, headers=headers)
    opener = urllib.request.build_opener(NoIdentityRedirect())
    with opener.open(request, timeout=5) as response:
        encoded = response.read(65537)
    if len(encoded) > 65536:
        raise ValueError("Identity response exceeds budget")
    return json.loads(encoded)


class NoIdentityRedirect(urllib.request.HTTPRedirectHandler):
    """Never forward identity credentials to another origin via redirects."""

    def redirect_request(self, request: urllib.request.Request, file_pointer: object,
                         code: int, message: str, headers: object, new_url: str) -> None:
        return None


@dataclass(frozen=True)
class KeycloakVerifier:
    """Use a dedicated confidential introspection client, not identity-admin credentials."""

    issuer: str
    internal_base: str
    resource: str
    client_id: str
    secret: str
    approved_clients: frozenset[str]

    async def introspect(self, token: str) -> dict[str, object] | None:
        """Recheck active account/session on every invocation; no token-validity cache."""
        if not token or len(token) > 10000 or not self.secret:
            return None
        try:
            return await asyncio.to_thread(identity_request, self.internal_base +
                "/protocol/openid-connect/token/introspect", {"token": token,
                "client_id": self.client_id, "client_secret": self.secret})
        except (OSError, ValueError, ProjectFailure):
            LOGGER.warning("Identity introspection unavailable; access denied")
            return None

    async def verify_token(self, token: str) -> AccessToken | None:
        """Only reviewed clients and this resource's active, verified-account tokens."""
        claims = await self.introspect(token)
        if claims is None or not valid_identity_claims(claims, self.issuer):
            return None
        client = str(claims.get("client_id", claims.get("azp", "")))
        audiences = claims.get("aud", [])
        audiences = [audiences] if isinstance(audiences, str) else audiences
        if client not in self.approved_clients or not isinstance(audiences, list) or self.resource not in audiences:
            return None
        scopes = str(claims.get("scope", "")).split()
        if "circuit:read" not in scopes:
            return None
        return AccessToken(token=token, client_id=client, subject=str(claims["sub"]),
                           scopes=scopes, expires_at=int(str(claims["exp"])), resource=self.resource,
                           claims={"iss": self.issuer, "iat": claims["iat"]})


def valid_identity_claims(claims: dict[str, object], issuer: str) -> bool:
    """Reject malformed, expired, unverified, wrong-issuer and inactive identities."""
    return (claims.get("active") is True and claims.get("iss") == issuer
            and claims.get("email_verified") is True
            and type(claims.get("exp")) is int and cast(int, claims["exp"]) > time.time()
            and type(claims.get("iat")) is int and 0 <= cast(int, claims["iat"]) <= time.time() + 5
            and isinstance(claims.get("sub"), str)
            and re.fullmatch(r"[a-zA-Z0-9._-]{1,80}", str(claims["sub"])) is not None)


def configured_verifier() -> KeycloakVerifier:
    """A missing deployment secret disables authentication instead of weakening it."""
    origin = public_url() or "http://127.0.0.1:8010"
    issuer = origin + "/auth/realms/circuit-lab"
    internal = os.environ.get("CIRCUIT_IDENTITY_INTERNAL_URL", issuer)
    if internal != issuer and internal != "http://identity:8080/auth/realms/circuit-lab":
        raise ValueError("Identity internal URL must be the configured issuer or the isolated identity service")
    return KeycloakVerifier(issuer, internal, origin + "/mcp",
        os.environ.get("CIRCUIT_MCP_INTROSPECTION_CLIENT", "circuit-lab-mcp-resource"),
        os.environ.get("CIRCUIT_MCP_INTROSPECTION_SECRET", ""),
        frozenset(filter(None, os.environ.get("CIRCUIT_MCP_CLIENTS", "").split(","))))


async def browser_principal(request: Request, verifier: KeycloakVerifier) -> Principal:
    """Local drafts use local identity; hosted writes require a fresh verified token."""
    correlation = str(request.state.correlation_id)
    if not public_url():
        return Principal("local", "user:local", correlation, scopes=PERMISSIONS)
    claims = await verifier.introspect(request.headers.get("x-circuit-access-token", ""))
    if claims is None or not valid_identity_claims(claims, verifier.issuer):
        raise ProjectFailure("Sign in again; active verified identity required", 401)
    owner = str(claims["sub"])
    if request.state.actor != "user:" + owner:
        raise ProjectFailure("Authenticated identity does not match the gateway", 403)
    return Principal(owner, "user:" + owner, correlation, scopes=PERMISSIONS, issued_at=int(str(claims["iat"])))


async def ai_principal(verifier: KeycloakVerifier, token: AccessToken | None) -> Principal:
    """Revalidate each tool/resource call, not merely its MCP initialization session."""
    checked = await verifier.verify_token(token.token) if token else None
    if checked is None or checked.subject is None:
        raise ProjectFailure("Active MCP OAuth authorization required", 401)
    scopes = frozenset(scope.removeprefix("circuit:") for scope in checked.scopes if scope.startswith("circuit:"))
    return Principal(checked.subject, "ai-agent:" + checked.client_id, str(uuid4()),
                     client=checked.client_id, scopes=scopes, issued_at=int((checked.claims or {})["iat"]))
