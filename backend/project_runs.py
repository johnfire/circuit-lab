"""Durable revision-bound asynchronous runs through the existing isolated solver."""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID, uuid4

import asyncpg
from pydantic import ValidationError

from backend.project_access import audit_action, authorize
from backend.project_database import ProjectDatabase, decode_record, encode_json
from backend.project_documents import get_document, remember, replay, retry_hash
from backend.project_measurements import Report
from backend.project_models import DocumentContents, Principal, ProjectFailure
from backend.schematic_ac_gateway import launch_ac
from backend.schematic_ac_models import ACRequest, ACResponse
from backend.schematic_models import SchematicRequest, SchematicResponse, StrictModel
from backend.simulation_engine import SimulationFailure
from backend.worker_gateway import launch_schematic

LOGGER = logging.getLogger("circuit-lab.runs")


class RunCommand(StrictModel):
    """Run only one acknowledged immutable snapshot, with replay-safe admission."""

    revision: UUID
    analysis: Literal["transient", "ac"]
    idempotency_key: UUID


@dataclass
class RunJobs:
    """Bounded background jobs owned and drained by the application's lifespan."""

    database: ProjectDatabase
    build_id: str
    pending: set[asyncio.Task[None]] = field(default_factory=set)

    async def close(self) -> None:
        """Let admitted bounded workers finish before closing their database pool."""
        if self.pending:
            await asyncio.gather(*tuple(self.pending), return_exceptions=True)


def run_snapshot(contents: DocumentContents, command: RunCommand, correlation: str) -> Report:
    """No user netlist, formula or shell input crosses the existing worker boundary."""
    circuit = SchematicRequest.model_validate(contents.circuit.model_dump())
    if command.analysis == "ac":
        if contents.sweep is None:
            raise ProjectFailure("Set an AC excitation before running a sweep")
        return launch_ac(ACRequest(circuit=circuit, sweep=contents.sweep), correlation)
    return launch_schematic(circuit, correlation)


async def run_budget(connection: asyncpg.Connection, principal: Principal) -> None:
    """One simultaneous job/account, two globally and bounded durable run storage."""
    counts = await connection.fetchrow(
            "SELECT count(*) FILTER (WHERE r.status='running') AS active, "
            "count(*) FILTER (WHERE d.owner=$1 AND r.status='running') AS own_active, "
            "count(*) FILTER (WHERE d.owner=$1 AND r.created_at>now()-interval '1 minute') AS recent, "
            "count(*) AS total FROM collaboration_runs r JOIN collaboration_documents d ON d.id=r.document",
        principal.owner)
    if counts is None or int(str(counts["active"])) >= 2 or int(str(counts["own_active"])) >= 1:
        raise ProjectFailure("Simulation busy; wait for the current run", 429)
    if int(str(counts["recent"])) >= 10 or int(str(counts["total"])) >= 2000:
        raise ProjectFailure("Simulation rate/storage quota reached", 429)


async def start_run(jobs: RunJobs, principal: Principal, document: UUID,
                    command: RunCommand) -> dict[str, object]:
    """Validate before admission, then return a durable run ID rather than holding SSE open."""
    snapshot = await get_document(jobs.database, principal, document, command.revision)
    contents = DocumentContents.model_validate(snapshot["contents"])
    SchematicRequest.model_validate(contents.circuit.model_dump())
    if command.analysis == "ac" and contents.sweep is None:
        raise ProjectFailure("Choose a valid AC excitation before simulation")
    fingerprint = retry_hash(document, command.model_dump(mode="json"))
    async with jobs.database.available_pool().acquire() as connection, connection.transaction():
        await authorize(connection, principal, document, "simulate")
        replayed = await replay(connection, principal, command.idempotency_key, fingerprint)
        if replayed is not None:
            return replayed
        await connection.execute("SELECT pg_advisory_xact_lock(582349106)")
        await run_budget(connection, principal)
        run = uuid4()
        await connection.execute(
            "INSERT INTO collaboration_runs(id,document,revision,analysis,settings,status,actor,correlation_id,build_id) "
            "VALUES($1,$2,$3,$4,$5::jsonb,'running',$6,$7,$8)", run, document, command.revision,
            command.analysis, contents.model_dump_json(), principal.actor, principal.correlation_id, jobs.build_id)
        await audit_action(connection, principal, document, "simulation.started", (command.revision, command.revision))
        response: dict[str, object] = {"run": str(run), "document": str(document), "revision": str(command.revision),
                    "status": "running", "analysis": command.analysis, "correlation_id": principal.correlation_id}
        await remember(connection, principal, (command.idempotency_key, fingerprint), response)
    task = asyncio.create_task(finish_run(jobs, principal, run, command))
    jobs.pending.add(task)
    task.add_done_callback(jobs.pending.discard)
    return response


async def finish_run(jobs: RunJobs, principal: Principal, run: UUID, command: RunCommand) -> None:
    """Recheck sharing before publishing a completed report; failures stay honest and durable."""
    try:
        async with jobs.database.available_pool().acquire() as connection:
            row = await connection.fetchrow("SELECT document,settings FROM collaboration_runs WHERE id=$1", run)
        if row is None:
            return
        document = UUID(str(row["document"]))
        report = await asyncio.to_thread(run_snapshot, DocumentContents.model_validate(decode_record(row["settings"])),
                                         command, principal.correlation_id)
        async with jobs.database.available_pool().acquire() as connection, connection.transaction():
            await authorize(connection, principal, document, "simulate")
            await connection.execute("UPDATE collaboration_runs SET status='completed',report=$2::jsonb WHERE id=$1",
                                     run, report.model_dump_json())
            await audit_action(connection, principal, document, "simulation.completed", (command.revision, command.revision))
    except (ProjectFailure, SimulationFailure, ValidationError, asyncpg.PostgresError, OSError, TimeoutError) as failure:
        LOGGER.warning("Simulation failed correlation=%s kind=%s", principal.correlation_id, type(failure).__name__)
        try:
            await record_run_failure(jobs, principal, run)
        except (ProjectFailure, asyncpg.PostgresError, OSError, TimeoutError):
            LOGGER.error("Cannot record failed simulation; recovery required correlation=%s", principal.correlation_id)


async def record_run_failure(jobs: RunJobs, principal: Principal, run: UUID) -> None:
    """Store no partial samples or private exception internals on a failed run."""
    async with jobs.database.available_pool().acquire() as connection, connection.transaction():
        document = await connection.fetchval("SELECT document FROM collaboration_runs WHERE id=$1", run)
        if document is not None:
            await connection.execute("UPDATE collaboration_runs SET status='failed',error=$2,report=NULL WHERE id=$1",
                                     run, "Simulation failed or sharing expired; validate and rerun")
            await audit_action(connection, principal, UUID(str(document)), "simulation.failed")


async def get_run(database: ProjectDatabase, principal: Principal,
                  document: UUID, run: UUID) -> dict[str, object]:
    """Every report and export is authorized independently, including after revocation."""
    async with database.available_pool().acquire() as connection, connection.transaction():
        await authorize(connection, principal, document, "read")
        row = await connection.fetchrow("SELECT * FROM collaboration_runs WHERE document=$1 AND id=$2", document, run)
        if row is None:
            raise ProjectFailure("Simulation not found", 404)
        response = decode_record(encode_json(dict(row)))
        response.pop("settings", None)
        response["report"] = decode_record(row["report"]) if row["report"] is not None else None
        response["provenance"] = "Real ngspice; generic ideal models, not manufacturer ratings or hardware approval"
        return response


async def get_report(database: ProjectDatabase, principal: Principal, document: UUID, run: UUID) -> Report:
    """Only completed validated solver evidence can feed numerical measurements."""
    saved = await get_run(database, principal, document, run)
    if saved["status"] != "completed":
        raise ProjectFailure("Simulation is not completed", 409)
    return (ACResponse.model_validate(saved["report"]) if saved["analysis"] == "ac"
            else SchematicResponse.model_validate(saved["report"]))


async def list_runs(database: ProjectDatabase, principal: Principal, document: UUID) -> list[dict[str, object]]:
    """Bounded run discovery without streaming all reports on every browser poll."""
    async with database.available_pool().acquire() as connection, connection.transaction():
        await authorize(connection, principal, document, "read")
        rows = await connection.fetch("SELECT id,revision,analysis,status,actor,created_at FROM collaboration_runs "
                                      "WHERE document=$1 ORDER BY created_at DESC LIMIT 20", document)
        return [decode_record(encode_json(dict(row))) for row in rows]


async def recover_interrupted_runs(database: ProjectDatabase) -> None:
    """Workers cannot survive an API restart; preserve failed evidence, never invent completion."""
    async with database.available_pool().acquire() as connection, connection.transaction():
        rows = await connection.fetch("UPDATE collaboration_runs SET status='interrupted',report=NULL, "
            "error='API restarted before completion; run this revision again' WHERE status='running' "
            "RETURNING document,revision,correlation_id")
        for row in rows:
            owner = await connection.fetchval("SELECT owner FROM collaboration_documents WHERE id=$1", row["document"])
            actor = Principal(str(owner), "service:run-recovery", str(row["correlation_id"]))
            revision = UUID(str(row["revision"]))
            await audit_action(connection, actor, UUID(str(row["document"])), "simulation.interrupted", (revision, revision))
