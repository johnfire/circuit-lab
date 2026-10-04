"""Browser-controlled, expiring delegation; the AI can never change permissions."""

from uuid import UUID, uuid4

from backend.project_access import audit_action, authorize
from backend.project_database import ProjectDatabase, decode_record, encode_json
from backend.project_models import NewGrant, Principal, ProjectFailure


def require_browser(principal: Principal) -> None:
    """Permission changes belong to a human, not a circuit-editing tool."""
    if principal.client is not None:
        raise ProjectFailure("Only the signed-in browser can change sharing", 403)


async def create_grant(database: ProjectDatabase, principal: Principal,
                       document: UUID, command: NewGrant,
                       approved_clients: frozenset[str]) -> dict[str, object]:
    """Require explicit target, verified OAuth client and short permissions lifetime."""
    require_browser(principal)
    if command.mode != "oauth" or command.client not in approved_clients:
        raise ProjectFailure("Choose a registered OAuth client; manual connection tokens are not enabled")
    async with database.available_pool().acquire() as connection, connection.transaction():
        await authorize(connection, principal, document, "edit")
        live = await connection.fetchval("SELECT count(*) FROM collaboration_grants WHERE document=$1 "
                                         "AND revoked_at IS NULL AND expires_at>clock_timestamp()", document)
        if int(str(live)) >= 10:
            raise ProjectFailure("Sharing quota reached; revoke an existing connection", 429)
        grant = uuid4()
        row = await connection.fetchrow(
            "INSERT INTO collaboration_grants(id,document,owner,client,scopes,mode,expires_at) "
            "VALUES($1,$2,$3,$4,$5,'oauth',clock_timestamp()+$6*interval '1 minute') "
            "RETURNING id,client,scopes,expires_at", grant, document, principal.owner,
            command.client, command.scopes, command.lifetime_minutes)
        if row is None:
            raise ProjectFailure("Sharing could not be saved", 503)
        await audit_action(connection, principal, document, "sharing.grant")
        return decode_record(encode_json(dict(row)))


async def revoke_grants(database: ProjectDatabase, principal: Principal, document: UUID) -> dict[str, object]:
    """One stop-sharing action revokes further reads, edits, jobs and view delivery."""
    require_browser(principal)
    async with database.available_pool().acquire() as connection, connection.transaction():
        await authorize(connection, principal, document, "edit")
        await connection.execute("UPDATE collaboration_grants SET revoked_at=clock_timestamp() "
                                 "WHERE document=$1 AND revoked_at IS NULL", document)
        await audit_action(connection, principal, document, "sharing.revoke")
        return {"status": "revoked", "document": str(document),
                "notice": "Revocation cannot erase content already received by an external AI provider"}


async def list_grants(database: ProjectDatabase, principal: Principal, document: UUID) -> list[dict[str, object]]:
    """Return connection metadata only, never bearer credentials or token digests."""
    require_browser(principal)
    async with database.available_pool().acquire() as connection, connection.transaction():
        await authorize(connection, principal, document, "read")
        rows = await connection.fetch("SELECT id,client,scopes,expires_at,revoked_at FROM collaboration_grants "
                                      "WHERE document=$1 ORDER BY created_at DESC LIMIT 30", document)
        return [decode_record(encode_json(dict(row))) for row in rows]
