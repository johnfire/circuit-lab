"""Native Keycloak deletion/password reconciliation and credential-free data export."""

import asyncio
import time
import urllib.error
import urllib.parse
from uuid import NAMESPACE_URL, UUID, uuid5

from backend.project_access import audit_action, lock_owner
from backend.project_database import ProjectDatabase, decode_record, encode_json, owner_hash
from backend.project_identity import KeycloakVerifier, identity_payload, identity_request
from backend.project_models import Principal, ProjectFailure


async def lifecycle_event(database: ProjectDatabase, owner: str, event: UUID,
                          change: tuple[str, int]) -> None:
    """Idempotently revoke old grants or cascade actual account deletion under its owner lock."""
    action, issued_after = change
    principal = Principal(owner, "identity:keycloak", str(event))
    async with database.available_pool().acquire() as connection, connection.transaction():
        await connection.execute("SELECT pg_advisory_xact_lock(hashtextextended($1,0))", owner)
        exists = await connection.fetchval("SELECT event_id FROM collaboration_identity_events WHERE event_id=$1", event)
        if exists is not None:
            return
        await connection.execute("INSERT INTO collaboration_identity_events(event_id,subject_hash,action) VALUES($1,$2,$3)",
                                 event, owner_hash(owner), action)
        await connection.execute("INSERT INTO collaboration_accounts(owner,enabled,minimum_token_iat) VALUES($1,$2,$3) "
                                 "ON CONFLICT(owner) DO UPDATE SET enabled=collaboration_accounts.enabled AND $2, "
                                 "minimum_token_iat=GREATEST(collaboration_accounts.minimum_token_iat,$3)",
                                 owner, action != "deleted", issued_after)
        await connection.execute("UPDATE collaboration_grants SET revoked_at=clock_timestamp() WHERE owner=$1 "
                                 "AND created_at<to_timestamp($2) AND revoked_at IS NULL", owner, issued_after)
        if action == "deleted":
            await connection.execute("DELETE FROM collaboration_documents WHERE owner=$1", owner)
            await connection.execute("DELETE FROM collaboration_retries WHERE owner=$1", owner)
        await audit_action(connection, principal, event, "account." + action)


async def reconcile_accounts(database: ProjectDatabase, verifier: KeycloakVerifier,
                              owner: str | None = None) -> None:
    """Dedicated view-users/view-events client; never an existing administrator's credentials."""
    issued = await asyncio.to_thread(identity_request, verifier.internal_base + "/protocol/openid-connect/token",
        {"grant_type": "client_credentials", "client_id": verifier.client_id, "client_secret": verifier.secret})
    bearer = str(issued.get("access_token", ""))
    if not bearer:
        raise ProjectFailure("Identity lifecycle connection unavailable", 503)
    async with database.available_pool().acquire() as connection:
        rows = (await connection.fetch("SELECT owner FROM collaboration_accounts WHERE enabled=true ORDER BY owner LIMIT 2000")
                if owner is None else [{"owner": owner}])
    admin_base = verifier.internal_base.replace("/realms/circuit-lab", "/admin/realms/circuit-lab")
    configuration = await asyncio.to_thread(identity_request, admin_base + "/events/config", {}, bearer)
    if configuration.get("eventsEnabled") is not True or configuration.get("adminEventsEnabled") is not True or configuration.get("adminEventsDetailsEnabled") is not False:
        raise ProjectFailure("Required private identity lifecycle recording is not enabled", 503)
    await asyncio.to_thread(identity_payload, admin_base + "/users?max=1", {}, bearer)
    await asyncio.to_thread(identity_payload, admin_base + "/events?max=1", {}, bearer)
    for row in rows:
        await reconcile_owner(database, admin_base, bearer, str(row["owner"]))


async def reconcile_owner(database: ProjectDatabase, admin_base: str, bearer: str, owner: str) -> None:
    """Observe one actual identity account and its password events, failing closed on errors."""
    try:
        await asyncio.to_thread(identity_request, admin_base + "/users/" + urllib.parse.quote(owner, safe=""), {}, bearer)
    except urllib.error.HTTPError as failure:
        if failure.code != 404:
            raise
        await lifecycle_event(database, owner, uuid5(NAMESPACE_URL, "circuit-lab/deleted/" + owner),
                              ("deleted", int(time.time()) + 1))
        return
    queries = ["/events?" + urllib.parse.urlencode(
        [("user", owner), ("type", "UPDATE_PASSWORD"), ("type", "RESET_PASSWORD"), ("max", "1")]),
        "/admin-events?" + urllib.parse.urlencode({"resourcePath": f"users/{owner}/reset-password", "max": "1"})]
    for endpoint in queries:
        events = await asyncio.to_thread(identity_payload, admin_base + endpoint, {}, bearer)
        if not isinstance(events, list):
            raise ProjectFailure("Identity lifecycle evidence unavailable", 503)
        if events:
            recorded = decode_record(events[0])
            epoch = int(str(recorded["time"])) // 1000 + 1
            await lifecycle_event(database, owner, uuid5(NAMESPACE_URL, f"circuit-lab/password/{owner}/{epoch}"),
                                  ("password_changed", epoch))


async def export_projects(database: ProjectDatabase, principal: Principal) -> dict[str, object]:
    """All account application content, without credentials or access-token digests."""
    if principal.client:
        raise ProjectFailure("Account export belongs to the signed-in browser", 403)
    async with database.available_pool().acquire() as connection, connection.transaction():
        await lock_owner(connection, principal)
        if "read" not in principal.scopes:
            raise ProjectFailure("Read permission required", 403)
        documents = await connection.fetch("SELECT * FROM collaboration_documents WHERE owner=$1", principal.owner)
        revisions = await connection.fetch("SELECT r.* FROM collaboration_revisions r JOIN collaboration_documents d "
                                           "ON d.id=r.document WHERE d.owner=$1", principal.owner)
        runs = await connection.fetch("SELECT r.* FROM collaboration_runs r JOIN collaboration_documents d "
                                      "ON d.id=r.document WHERE d.owner=$1", principal.owner)
        grants = await connection.fetch("SELECT id,document,client,scopes,mode,expires_at,revoked_at,created_at "
                                        "FROM collaboration_grants WHERE owner=$1", principal.owner)
        actions = await connection.fetch("SELECT * FROM collaboration_actions WHERE owner_hash=$1", owner_hash(principal.owner))
        return {name: [decode_record(encode_json(dict(row))) for row in rows] for name, rows in
                (("documents", documents), ("revisions", revisions), ("runs", runs), ("grants", grants), ("actions", actions))}
