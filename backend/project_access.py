"""The shared REST/MCP authorization and immutable audit boundary."""

from collections.abc import Mapping
from uuid import UUID, uuid4

import asyncpg

from backend.project_database import owner_hash
from backend.project_models import Principal, ProjectFailure


async def lock_owner(connection: asyncpg.Connection, principal: Principal) -> None:
    """Serialize content/grant/lifecycle changes per owner, with no process-local lock."""
    await connection.execute("SELECT pg_advisory_xact_lock(hashtextextended($1, 0))", principal.owner)
    account = await connection.fetchrow("SELECT * FROM collaboration_accounts WHERE owner=$1", principal.owner)
    if account is not None and (not account["enabled"] or
                               (principal.issued_at or 0) < int(str(account["minimum_token_iat"]))):
        raise ProjectFailure("Account access was revoked; sign in again", 403)


async def authorize(connection: asyncpg.Connection, principal: Principal,
                    document: UUID, permission: str) -> Mapping[str, object]:
    """A guessed UUID, browser actor header or MCP annotation never grants access."""
    await lock_owner(connection, principal)
    if permission not in principal.scopes:
        raise ProjectFailure("Connection lacks this permission", 403)
    owned = await connection.fetchrow("SELECT * FROM collaboration_documents WHERE id=$1 AND owner=$2",
                                      document, principal.owner)
    if owned is None:
        raise ProjectFailure("Circuit not found or not shared", 404)
    if principal.client:
        grant = await connection.fetchval(
            "SELECT id FROM collaboration_grants WHERE document=$1 AND owner=$2 AND client=$3 "
            "AND mode='oauth' AND revoked_at IS NULL AND expires_at>clock_timestamp() AND $4=ANY(scopes)",
            document, principal.owner, principal.client, permission)
        if grant is None:
            raise ProjectFailure("Circuit not found or sharing has expired", 404)
    return owned


async def audit_action(connection: asyncpg.Connection, principal: Principal,
                       target: UUID, action: str, revisions: tuple[UUID | None, UUID | None] = (None, None)) -> None:
    """Write correct human/AI attribution in the same transaction as its mutation."""
    await connection.execute(
        "INSERT INTO collaboration_actions(id,owner_hash,target,actor,action,before_revision,"
        "after_revision,correlation_id) VALUES($1,$2,$3,$4,$5,$6,$7,$8)",
        uuid4(), owner_hash(principal.owner), target, principal.actor, action,
        revisions[0], revisions[1], principal.correlation_id)
