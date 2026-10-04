"""Reviewed client configuration never grants passwords, wildcards or administrator writes."""

import pytest

from deploy.mcp_identity_configuration import oauth_additions, reviewed_client


def test_codex_reviewed_pkce_configuration():
    configured = oauth_additions("https://circuit-lab.christopherrehm.de", "http://127.0.0.1:8124/callback", "circuit-lab-codex")
    client = configured["clients"][0]
    assert client["publicClient"] and client["consentRequired"]
    assert not client["directAccessGrantsEnabled"] and not client["serviceAccountsEnabled"]
    assert client["redirectUris"] == ["http://127.0.0.1:8124/callback"]
    assert client["protocolMappers"][0]["config"]["included.custom.audience"].endswith("/mcp")
    assert configured["serviceAccountRoleMappings"]["circuit-lab-mcp-resource"]["realm-management"] == ["view-users", "view-events"]


@pytest.mark.parametrize("callback", ["https://example.test/*", "http://example.test/callback", "http://127.0.0.1:8124/callback#code",
                                     "https://user:password@example.test/callback"])
def test_reject_unreviewable_oauth_callbacks(callback):
    with pytest.raises(ValueError):
        reviewed_client("https://circuit-lab.christopherrehm.de", callback, "circuit-lab-codex")
