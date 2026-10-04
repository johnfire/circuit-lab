"""Real SDK plus PostgreSQL and genuine solver: shared-circuit AI editing and evidence."""

import asyncio
from uuid import UUID, uuid4

import pytest
from mcp import Client
from mcp.server import MCPServer

from backend.mcp_projects import register_collaboration
from backend.project_database import ProjectDatabase
from backend.project_documents import get_document, mutate_document
from backend.project_grants import create_grant, revoke_grants
from backend.project_identity import PERMISSIONS
from backend.project_models import DocumentContents, NewGrant, Principal, ReplaceDocument
from backend.project_runtime import CollaborationRuntime
from backend.schematic_ac_models import Sweep
from tests.test_project_services import (
    browser_identity,
    database_session,
    edit_command,
    saved_circuit,
)


def test_real_sdk_edits_simulates_measures_restores_and_cannot_reuse_revoked_access(project_database_url, analog_request):
    async def scenario():
        async with database_session(project_database_url) as database:
            owner = browser_identity()
            saved = await saved_circuit(database, owner, analog_request)
            document = UUID(saved["document"])
            ai = Principal(owner.owner, "ai-agent:codex-test", uuid4().hex, client="codex-test",
                           scopes=PERMISSIONS, issued_at=owner.issued_at)
            await create_grant(database, owner, document, NewGrant(client="codex-test", scopes=list(PERMISSIONS),
                               lifetime_minutes=5), frozenset({"codex-test"}))
            runtime = CollaborationRuntime(database=ProjectDatabase(database.available_pool()), identity_ready=True)
            server = MCPServer("real-test")
            async def principal():
                return ai
            register_collaboration(server, runtime, principal)
            async with Client(server) as client:
                discovered = {tool.name for tool in (await client.list_tools()).tools}
                assert {"get_circuit", "apply_circuit_edits", "undo_last_change", "simulate_circuit", "read_samples"} <= discovered
                assert not {"delete_project", "create_grant", "shell", "execute_code"} & discovered
                command = edit_command(saved["revision"])
                edited = await client.call_tool("apply_circuit_edits", {"document": str(document), "command": command.model_dump(mode="json")})
                assert not edited.is_error and edited.structured_content["actor"] == "ai-agent:codex-test"
                head = edited.structured_content["revision"]
                await run_and_measure(client, runtime, document, head)
                undo = await client.call_tool("undo_last_change", {"document": str(document), "command": {
                    "expected_revision": head, "idempotency_key": str(uuid4()), "reason": "Undo AI change"}})
                assert not undo.is_error and undo.structured_content["contents"] == saved["contents"]
                await revoke_grants(database, owner, document)
                denied = await client.call_tool("get_circuit", {"document": str(document)})
                assert denied.is_error and "expired" in str(denied.content)
                with pytest.raises(Exception, match="resource unavailable or not shared"):
                    await client.read_resource(f"circuit-lab://circuits/{document}/{head}")
                assert (await get_document(database, owner, document))["revision"] == undo.structured_content["revision"]
    asyncio.run(scenario())


async def run_and_measure(client: Client, runtime: CollaborationRuntime, document: UUID, revision: str):
    running = await client.call_tool("simulate_circuit", {"document": str(document), "command": {
        "revision": revision, "analysis": "transient", "idempotency_key": str(uuid4())}})
    assert not running.is_error
    await runtime.jobs.close()
    run = running.structured_content["run"]
    completed = await client.call_tool("get_simulation", {"document": str(document), "run": run})
    assert completed.structured_content["status"] == "completed"
    assert "I:R1" in completed.structured_content["signals"]
    query = {"signal": {"kind": "current", "first": {"part": "R1", "terminal": 0}}, "start": 0, "stop": .03}
    measured = await client.call_tool("measure_signals", {"document": str(document), "run": run, "query": query})
    assert measured.structured_content["unit"] == "A" and measured.structured_content["samples"] > 10
    assert measured.structured_content["rms"] > 0
    samples = await client.call_tool("read_samples", {"document": str(document), "run": run,
        "query": {"signal": query["signal"], "limit": 3}})
    assert len(samples.structured_content["real"]) == 3
    assert samples.structured_content["decimated"] is False


def test_real_sdk_ac_preserves_complex_samples_and_excitation_relative_phase(project_database_url, analog_request):
    async def scenario():
        async with database_session(project_database_url) as database:
            owner = browser_identity()
            saved = await saved_circuit(database, owner, analog_request)
            document = UUID(str(saved["document"]))
            contents = DocumentContents.model_validate(saved["contents"])
            sweep = Sweep(source="V1", amplitude=2, phase=37, start=10, stop=1000, points=10, spacing="log")
            updated = await mutate_document(database, owner, document, ReplaceDocument(expected_revision=UUID(str(saved["revision"])),
                idempotency_key=uuid4(), reason="Set explicit AC excitation", contents=contents.model_copy(update={"sweep": sweep})))
            runtime = CollaborationRuntime(database=database, identity_ready=True)
            server = MCPServer("real-ac-test")
            async def principal():
                return owner
            register_collaboration(server, runtime, principal)
            async with Client(server) as client:
                running = await client.call_tool("simulate_circuit", {"document": str(document), "command": {
                    "revision": updated["revision"], "analysis": "ac", "idempotency_key": str(uuid4())}})
                assert not running.is_error
                await runtime.jobs.close()
                run = running.structured_content["run"]
                signal = {"kind": "node", "first": {"part": "C1", "terminal": 0}}
                samples = await client.call_tool("read_samples", {"document": str(document), "run": run,
                    "query": {"signal": signal, "limit": 3}})
                assert len(samples.structured_content["imaginary"]) == 3 and samples.structured_content["axis_unit"] == "Hz"
                measured = await client.call_tool("measure_signals", {"document": str(document), "run": run,
                    "query": {"signal": signal, "start": 10, "stop": 1000}})
                evidence = measured.structured_content
                assert evidence["phase_reference"] == "AC excitation" and "rms" not in evidence
                assert evidence["first_phase_degrees"] == pytest.approx(-32.1419, abs=.001)
                assert evidence["last_phase_degrees"] == pytest.approx(-89.0882, abs=.001)
    asyncio.run(scenario())
