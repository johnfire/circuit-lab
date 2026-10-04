"""Generate reviewed OAuth additions, not a replacement for an existing live realm."""

import json
import sys
import urllib.parse

SCOPES = ("read", "edit", "simulate", "view")


def reviewed_client(origin: str, callback: str, identifier: str) -> dict[str, object]:
    """Fixed HTTPS resource and exact PKCE callback; no DCR, wildcard or password grant."""
    public = urllib.parse.urlparse(origin)
    redirect = urllib.parse.urlparse(callback)
    if public.scheme != "https" or not public.hostname or public.path not in {"", "/"} or public.username or public.query or public.fragment:
        raise ValueError("Resource origin must be HTTPS without a path")
    if "*" in callback or redirect.username or redirect.fragment or not redirect.hostname:
        raise ValueError("Use the exact reviewed callback, never a wildcard")
    if redirect.scheme != "https" and not (redirect.scheme == "http" and redirect.hostname == "127.0.0.1"):
        raise ValueError("Only HTTPS or an exact IPv4 loopback callback is allowed")
    if not identifier or len(identifier) > 80 or not all(character.isalnum() or character in "._-" for character in identifier):
        raise ValueError("Invalid reviewed OAuth client ID")
    return {"clientId": identifier, "name": "Circuit Lab · " + identifier, "enabled": True,
        "protocol": "openid-connect", "publicClient": True, "standardFlowEnabled": True,
        "directAccessGrantsEnabled": False, "serviceAccountsEnabled": False, "consentRequired": True,
        "redirectUris": [callback], "webOrigins": [], "fullScopeAllowed": False,
        "defaultClientScopes": ["basic", "profile", "email", *["circuit:" + scope for scope in SCOPES]],
        "attributes": {"pkce.code.challenge.method": "S256"}, "protocolMappers": [{
            "name": "circuit-lab-resource", "protocol": "openid-connect", "protocolMapper": "oidc-audience-mapper",
            "config": {"included.custom.audience": origin.rstrip("/") + "/mcp", "access.token.claim": "true",
                       "introspection.token.claim": "true"}}, introspection_audience()]}


def introspection_audience() -> dict[str, object]:
    """Keycloak 26.8 checks the introspecting client's audience independently of the MCP URI."""
    return {"name": "circuit-lab-introspection", "protocol": "openid-connect", "protocolMapper": "oidc-audience-mapper",
            "config": {"included.client.audience": "circuit-lab-mcp-resource", "access.token.claim": "true",
                       "introspection.token.claim": "true"}}


def oauth_additions(origin: str, callback: str, identifier: str) -> dict[str, object]:
    """Operator applies only these new entries and read-only service-account roles."""
    return {"clients": [reviewed_client(origin, callback, identifier), {
        "clientId": "circuit-lab-mcp-resource", "name": "Circuit Lab introspection and lifecycle",
        "enabled": True, "protocol": "openid-connect", "publicClient": False,
        "secret": "${CIRCUIT_MCP_INTROSPECTION_SECRET}", "standardFlowEnabled": False,
        "directAccessGrantsEnabled": False, "serviceAccountsEnabled": True,
        "fullScopeAllowed": False, "defaultClientScopes": ["roles"], "redirectUris": []}],
        "clientScopes": [{"name": "circuit:" + scope, "protocol": "openid-connect",
                          "attributes": {"include.in.token.scope": "true", "display.on.consent.screen": "true"}}
                         for scope in SCOPES],
        "serviceAccountRoleMappings": {"circuit-lab-mcp-resource": {"realm-management": ["view-users", "view-events"]}},
        "serviceAccountScopeMappings": {"circuit-lab-mcp-resource": {"realm-management": ["view-users", "view-events"]}},
        "existingClientAdditions": {"circuit-lab-web": {"protocolMappers": [introspection_audience()], "addDefaultClientScopes": ["basic"]}},
        "requiredRealmSettings": {"eventsEnabled": True, "adminEventsEnabled": True, "adminEventsDetailsEnabled": False}}


if __name__ == "__main__":
    print(json.dumps(oauth_additions(*sys.argv[1:4]), indent=2))
