"""Private snapshots, atomic revision writes and replay-safe non-destructive undo."""

import hashlib
from collections.abc import Mapping
from uuid import UUID, uuid4

import asyncpg

from backend.project_access import audit_action, authorize, lock_owner
from backend.project_database import ProjectDatabase, decode_record, encode_json
from backend.project_models import (
    DocumentContents,
    EditDocument,
    NewDocument,
    Principal,
    ProjectFailure,
    ReplaceDocument,
    RestoreDocument,
    RevisionCommand,
    apply_edits,
    contents_hash,
)


async def list_documents(database: ProjectDatabase, principal: Principal,
                         kind: str, offset: int = 0) -> list[dict[str, object]]:
    """List only owned documents or the verified client's explicitly live grants."""
    if not 0 <= offset <= 1000 or kind not in {"project", "workspace"}:
        raise ProjectFailure("Invalid list window")
    async with database.available_pool().acquire() as connection, connection.transaction():
        await lock_owner(connection, principal)
        if "read" not in principal.scopes:
            raise ProjectFailure("Read permission required", 403)
        rows = await connection.fetch(
            "SELECT d.id,d.name,d.kind,d.head AS revision,d.updated_at FROM collaboration_documents d "
            "WHERE d.owner=$1 AND d.kind=$2 AND ($3::text IS NULL OR EXISTS (SELECT 1 FROM "
            "collaboration_grants g WHERE g.document=d.id AND g.owner=d.owner AND g.client=$3 "
            "AND g.mode='oauth' AND g.revoked_at IS NULL AND g.expires_at>clock_timestamp() "
            "AND 'read'=ANY(g.scopes))) ORDER BY d.updated_at DESC,d.id LIMIT 30 OFFSET $4",
            principal.owner, kind, principal.client, offset)
        return [decode_record(encode_json(dict(row))) for row in rows]


async def read_snapshot(connection: asyncpg.Connection, document: UUID,
                        revision: UUID) -> dict[str, object]:
    """Every historical snapshot must belong to the already-authorized document."""
    row = await connection.fetchrow(
        "SELECT r.*,d.name,d.kind FROM collaboration_revisions r JOIN collaboration_documents d "
        "ON d.id=r.document WHERE r.document=$1 AND r.id=$2", document, revision)
    if row is None:
        raise ProjectFailure("Revision not found", 404)
    snapshot = decode_record(encode_json(dict(row)))
    snapshot["contents"] = decode_record(row["contents"])
    snapshot["revision"] = str(revision)
    snapshot["sync"] = "Acknowledged server snapshot; unsent browser edits are not included"
    return snapshot


async def get_document(database: ProjectDatabase, principal: Principal, document: UUID,
                       revision: UUID | None = None) -> dict[str, object]:
    """Read current or historical contents without conflating browser tabs."""
    async with database.available_pool().acquire() as connection, connection.transaction():
        owned = await authorize(connection, principal, document, "read")
        return await read_snapshot(connection, document, revision or UUID(str(owned["head"])))


async def check_document_budget(connection: asyncpg.Connection, principal: Principal) -> None:
    """Bound account/global graph storage before allocating immutable snapshots."""
    owned = await connection.fetchval("SELECT count(*) FROM collaboration_documents WHERE owner=$1", principal.owner)
    total = await connection.fetchval("SELECT count(*) FROM collaboration_documents")
    if int(str(owned)) >= 20 or int(str(total)) >= 2000:
        raise ProjectFailure("Saved circuit quota reached; export your work locally", 429)


async def insert_revision(connection: asyncpg.Connection, principal: Principal,
                          document: UUID, snapshot: DocumentContents,
                          ancestry: tuple[UUID, UUID | None, str]) -> None:
    """One immutable complete snapshot, with verified actor and causal parent."""
    revision, parent, reason = ancestry
    await connection.execute(
        "INSERT INTO collaboration_revisions(id,document,parent,contents,contents_hash,actor,reason,"
        "correlation_id) VALUES($1,$2,$3,$4::jsonb,$5,$6,$7,$8)", revision, document, parent,
        snapshot.model_dump_json(), contents_hash(snapshot), principal.actor, reason, principal.correlation_id)


def retry_hash(document: UUID | None, command: object) -> str:
    """Bind retry identity to the target, command kind and exact bounded payload."""
    return hashlib.sha256(encode_json([document, command]).encode()).hexdigest()


async def replay(connection: asyncpg.Connection, principal: Principal,
                 key: UUID, fingerprint: str) -> dict[str, object] | None:
    """Reusing a key with different input is a conflict, never a different mutation."""
    row = await connection.fetchrow(
        "SELECT request_hash,response FROM collaboration_retries WHERE owner=$1 AND actor=$2 AND request_key=$3",
        principal.owner, principal.actor, key)
    if row is None:
        return None
    if row["request_hash"] != fingerprint:
        raise ProjectFailure("Idempotency key already used for a different request", 409)
    return decode_record(row["response"])


async def remember(connection: asyncpg.Connection, principal: Principal,
                   retry: tuple[UUID, str], response: dict[str, object]) -> dict[str, object]:
    """Record retry output atomically with its revision and audit event."""
    await connection.execute(
        "INSERT INTO collaboration_retries(owner,actor,request_key,request_hash,response) VALUES($1,$2,$3,$4,$5::jsonb)",
        principal.owner, principal.actor, retry[0], retry[1], encode_json(response))
    return response


async def create_document(database: ProjectDatabase, principal: Principal,
                          command: NewDocument) -> dict[str, object]:
    """Only the signed-in browser can create unshared account content."""
    if principal.client or "edit" not in principal.scopes:
        raise ProjectFailure("Create a private project in the browser, then share it explicitly", 403)
    fingerprint = retry_hash(None, command.model_dump(mode="json"))
    async with database.available_pool().acquire() as connection, connection.transaction():
        await lock_owner(connection, principal)
        replayed = await replay(connection, principal, command.idempotency_key, fingerprint)
        if replayed is not None:
            return replayed
        await check_revision_budget(connection)
        await check_document_budget(connection, principal)
        document, revision = uuid4(), uuid4()
        await connection.execute(
            "INSERT INTO collaboration_accounts(owner) VALUES($1) ON CONFLICT DO NOTHING", principal.owner)
        await connection.execute(
            "INSERT INTO collaboration_documents(id,owner,name,kind,head) VALUES($1,$2,$3,$4,$5)",
            document, principal.owner, command.name, command.kind, revision)
        await insert_revision(connection, principal, document, command.contents, (revision, None, "Created circuit"))
        await audit_action(connection, principal, document, "document.create", (None, revision))
        response = await read_snapshot(connection, document, revision)
        return await remember(connection, principal, (command.idempotency_key, fingerprint), response)


async def replacement_contents(connection: asyncpg.Connection, document: UUID,
                               current: Mapping[str, object],
                               command: RevisionCommand) -> DocumentContents:
    """Edits and restores use the same fully validated immutable revision contents."""
    existing = DocumentContents.model_validate(decode_record(current["contents"]))
    if isinstance(command, EditDocument):
        return apply_edits(existing, command.edits)
    if isinstance(command, ReplaceDocument):
        return command.contents
    if isinstance(command, RestoreDocument):
        restored = await read_snapshot(connection, document, command.revision)
        return DocumentContents.model_validate(restored["contents"])
    parent = current["parent"]
    if parent is None:
        raise ProjectFailure("There is no previous revision to undo", 409)
    restored = await read_snapshot(connection, document, UUID(str(parent)))
    return DocumentContents.model_validate(restored["contents"])


async def mutate_document(database: ProjectDatabase, principal: Principal,
                          document: UUID, command: RevisionCommand) -> dict[str, object]:
    """CAS, authorization, graph validation, history, audit and retries share a transaction."""
    fingerprint = retry_hash(document, [type(command).__name__, command.model_dump(mode="json")])
    async with database.available_pool().acquire() as connection, connection.transaction():
        owned = await authorize(connection, principal, document, "edit")
        replayed = await replay(connection, principal, command.idempotency_key, fingerprint)
        if replayed is not None:
            return replayed
        if str(owned["head"]) != str(command.expected_revision):
            raise ProjectFailure(f"Revision conflict; reread current head {owned['head']}", 409)
        count = await connection.fetchval("SELECT count(*) FROM collaboration_revisions WHERE document=$1", document)
        if int(str(count)) >= 250:
            raise ProjectFailure("Revision quota reached; export this project", 429)
        await check_revision_budget(connection)
        current = await connection.fetchrow("SELECT * FROM collaboration_revisions WHERE id=$1", command.expected_revision)
        if current is None:
            raise ProjectFailure("Current revision unavailable", 503)
        snapshot = await replacement_contents(connection, document, current, command)
        revision = uuid4()
        await insert_revision(connection, principal, document, snapshot,
                              (revision, command.expected_revision, command.reason))
        await connection.execute("UPDATE collaboration_documents SET head=$2,updated_at=now() WHERE id=$1",
                                 document, revision)
        await audit_action(connection, principal, document, type(command).__name__,
                           (command.expected_revision, revision))
        await authorize(connection, principal, document, "edit")
        response = await read_snapshot(connection, document, revision)
        return await remember(connection, principal, (command.idempotency_key, fingerprint), response)


async def list_revisions(database: ProjectDatabase, principal: Principal,
                         document: UUID, offset: int = 0) -> list[dict[str, object]]:
    """Bounded immutable history with human/AI authors and reasons, not secret credentials."""
    if not 0 <= offset <= 250:
        raise ProjectFailure("Invalid history window")
    async with database.available_pool().acquire() as connection, connection.transaction():
        await authorize(connection, principal, document, "read")
        rows = await connection.fetch(
            "SELECT id AS revision,parent,actor,reason,created_at,correlation_id FROM collaboration_revisions "
            "WHERE document=$1 ORDER BY created_at DESC,id DESC LIMIT 30 OFFSET $2", document, offset)
        return [decode_record(encode_json(dict(row))) for row in rows]


async def check_revision_budget(connection: asyncpg.Connection) -> None:
    """Bound aggregate immutable history across accounts, not only one document."""
    await connection.execute("SELECT pg_advisory_xact_lock(582349107)")
    count = await connection.fetchval("SELECT count(*) FROM collaboration_revisions")
    if int(str(count)) >= 10000:
        raise ProjectFailure("Application history storage quota reached; contact the operator", 429)
