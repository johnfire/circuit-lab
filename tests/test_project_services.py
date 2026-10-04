"""Real database isolation, atomicity, concurrency, undo and native lifecycle evidence."""

import asyncio
import time
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

import pytest

from backend.project_database import ProjectDatabase, connect_database
from backend.project_documents import (
    create_document,
    get_document,
    list_documents,
    list_revisions,
    mutate_document,
)
from backend.project_grants import create_grant, revoke_grants
from backend.project_identity import PERMISSIONS
from backend.project_lifecycle import export_projects, lifecycle_event
from backend.project_models import (
    DocumentContents,
    EditDocument,
    EditorCircuit,
    NewDocument,
    NewGrant,
    Principal,
    ProjectFailure,
    RevisionCommand,
)
from backend.schematic_models import SchematicRequest


@asynccontextmanager
async def database_session(url: str):
    database = ProjectDatabase(await connect_database(url))
    try:
        yield database
    finally:
        await database.available_pool().close()


def browser_identity() -> Principal:
    owner = "test-" + uuid4().hex
    return Principal(owner, "user:" + owner, uuid4().hex, scopes=PERMISSIONS, issued_at=int(time.time()))


async def saved_circuit(database: ProjectDatabase, owner: Principal, circuit: SchematicRequest):
    return await create_document(database, owner, NewDocument(name="Private circuit", idempotency_key=uuid4(),
        contents=DocumentContents(circuit=EditorCircuit.model_validate(circuit.model_dump()))))


def edit_command(revision: object, value: float = 2200) -> EditDocument:
    return EditDocument.model_validate({"expected_revision": str(revision), "idempotency_key": str(uuid4()),
        "reason": "Retune resistor", "edits": [{"operation": "put_part", "part":
        {"id": "R1", "kind": "R", "value": value, "x": 16, "y": 6}}]})


def test_real_private_grants_revocation_and_cross_owner_ids(project_database_url, analog_request):
    async def scenario():
        async with database_session(project_database_url) as database:
            owner, other = browser_identity(), browser_identity()
            saved = await saved_circuit(database, owner, analog_request)
            document = UUID(saved["document"])
            ai = Principal(owner.owner, "ai-agent:codex-test", uuid4().hex, client="codex-test",
                           scopes=PERMISSIONS, issued_at=owner.issued_at)
            for denied in (other, ai):
                with pytest.raises(ProjectFailure, match="not found"):
                    await get_document(database, denied, document)
            assert await list_documents(database, ai, "project") == []
            await create_grant(database, owner, document, NewGrant(client="codex-test", scopes=["read", "edit"],
                               lifetime_minutes=5), frozenset({"codex-test"}))
            assert len(await list_documents(database, ai, "project")) == 1
            assert (await get_document(database, ai, document))["revision"] == saved["revision"]
            with pytest.raises(ProjectFailure, match="Only"):
                await revoke_grants(database, ai, document)
            await revoke_grants(database, owner, document)
            with pytest.raises(ProjectFailure, match="sharing has expired"):
                await get_document(database, ai, document)
    asyncio.run(scenario())


def test_real_atomic_edit_cas_retry_and_non_destructive_undo(project_database_url, analog_request):
    async def scenario():
        async with database_session(project_database_url) as database:
            owner = browser_identity()
            saved = await saved_circuit(database, owner, analog_request)
            document = UUID(saved["document"])
            first, second = edit_command(saved["revision"]), edit_command(saved["revision"], 4700)
            attempts = await asyncio.gather(mutate_document(database, owner, document, first),
                mutate_document(database, owner, document, second), return_exceptions=True)
            completed = [attempt for attempt in attempts if isinstance(attempt, dict)]
            refused = [attempt for attempt in attempts if isinstance(attempt, ProjectFailure)]
            assert len(completed) == len(refused) == 1 and refused[0].status == 409
            command = first if completed[0]["contents"]["circuit"]["parts"][-1]["value"] == 2200 else second
            replayed = await mutate_document(database, owner, document, command)
            assert replayed["revision"] == completed[0]["revision"]
            changed_key = command.model_copy(update={"reason": "different payload"})
            with pytest.raises(ProjectFailure, match="Idempotency"):
                await mutate_document(database, owner, document, changed_key)
            restored = await mutate_document(database, owner, document, RevisionCommand(expected_revision=UUID(replayed["revision"]),
                idempotency_key=uuid4(), reason="Undo test"))
            assert restored["contents"] == saved["contents"]
            assert restored["revision"] != saved["revision"]
            assert len(await list_revisions(database, owner, document)) == 3
    asyncio.run(scenario())


def test_real_password_revocation_deletion_cascade_and_export(project_database_url, analog_request):
    async def scenario():
        async with database_session(project_database_url) as database:
            owner = browser_identity()
            saved = await saved_circuit(database, owner, analog_request)
            document = UUID(saved["document"])
            exported = await export_projects(database, owner)
            assert len(exported["documents"]) == 1
            assert "token_hash" not in str(exported)
            event = uuid4()
            await lifecycle_event(database, owner.owner, event, ("password_changed", int(time.time()) + 1))
            await lifecycle_event(database, owner.owner, event, ("password_changed", int(time.time()) + 1))
            with pytest.raises(ProjectFailure, match="revoked"):
                await get_document(database, owner, document)
            await lifecycle_event(database, owner.owner, uuid4(), ("deleted", int(time.time()) + 2))
            async with database.available_pool().acquire() as connection:
                assert await connection.fetchval("SELECT count(*) FROM collaboration_documents WHERE owner=$1", owner.owner) == 0
                assert await connection.fetchval("SELECT count(*) FROM collaboration_revisions WHERE document=$1", document) == 0
                assert await connection.fetchval("SELECT count(*) FROM collaboration_retries WHERE owner=$1", owner.owner) == 0
    asyncio.run(scenario())
