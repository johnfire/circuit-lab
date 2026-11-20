"""Configure only the disposable loopback identity for the native language browser tests."""

import json
from pathlib import Path
from uuid import uuid4

from deploy.identity_localization import migrate_localization
from deploy.staging_identity import RealmAdmin, configure_identity

ORIGIN = "https://127.0.0.1:8447"


def main() -> None:
    settings = dict(line.split("=", 1) for line in Path("deploy/identity-test.env").read_text().splitlines()
                    if line and not line.startswith("#"))
    fixture = dict(line.split("=", 1) for line in Path("deploy/identity-language-test.env").read_text().splitlines()
                   if line and not line.startswith("#"))
    configure_identity("http://127.0.0.1:8104", ORIGIN, settings["CIRCUIT_IDENTITY_ADMIN_PASSWORD"],
                       fixture["CIRCUIT_MCP_INTROSPECTION_SECRET"], fixture["CIRCUIT_MCP_CLIENTS"])
    admin = RealmAdmin("http://127.0.0.1:8104", settings["CIRCUIT_IDENTITY_ADMIN_PASSWORD"])
    migrate_localization(admin, Path("/tmp/circuit-identity-locale-" + str(uuid4()) + ".json"))
    client = "/clients/" + admin.require_client("circuit-lab-web")
    admin.request(client, {"redirectUris": [ORIGIN + "/oauth2/callback"], "webOrigins": [ORIGIN],
                          "attributes": {"pkce.code.challenge.method": "S256",
                                         "post.logout.redirect.uris": ORIGIN + "/*"}}, "PUT")
    admin.request("", {"smtpServer": {"host": "test-mail", "port": "1025", "auth": "true", "ssl": "false",
        "starttls": "false", "from": settings["CIRCUIT_SMTP_USER"], "fromDisplayName": "Circuit Lab",
        "user": settings["CIRCUIT_SMTP_USER"], "password": settings["CIRCUIT_SMTP_PASSWORD"]}}, "PUT")
    print(json.dumps({"browser_origin": ORIGIN, "mail": "isolated Mailpit", "ready": True}))


if __name__ == "__main__":
    main()
