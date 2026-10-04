"""MCP circuit tools/resources, all using the authenticated shared application services."""

import json
from collections.abc import Awaitable, Callable
from uuid import UUID

from mcp.server import MCPServer
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.mcpserver.exceptions import ResourceError
from mcp_types import ToolAnnotations
from pydantic import ValidationError

from backend.mcp_errors import guard_handler
from backend.mcp_orientation import register_orientation
from backend.project_documents import get_document, list_documents, list_revisions, mutate_document
from backend.project_identity import ai_principal
from backend.project_inspection import compare_contents, inspect_contents
from backend.project_measurements import (
    IntentCheck,
    MeasurementQuery,
    SampleQuery,
    evaluate_check,
    measure,
    sample_page,
)
from backend.project_models import (
    DocumentContents,
    EditDocument,
    Principal,
    ProjectFailure,
    ReplaceDocument,
    RestoreDocument,
    RevisionCommand,
)
from backend.project_runs import RunCommand, get_report, get_run, list_runs, start_run
from backend.project_runtime import CollaborationRuntime
from backend.project_views import ObservationCommand, set_view, view_status

PrincipalProvider = Callable[[], Awaitable[Principal]]
READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=False)
WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
JOB = ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=False)


def register_collaboration(server: MCPServer[None], runtime: CollaborationRuntime,
                            principal_provider: PrincipalProvider | None = None) -> None:
    """Identity injection is for real service tests; public calls always reverify OAuth."""
    async def principal() -> Principal:
        if principal_provider is not None:
            return await principal_provider()
        runtime.require_ready()
        actor = await ai_principal(runtime.verifier, get_access_token())
        await runtime.check_identity(actor)
        return actor

    register_orientation(server, runtime)
    register_circuit_tools(server, runtime, principal)
    register_history_tools(server, runtime, principal)
    register_run_tools(server, runtime, principal)
    register_resources(server, runtime, principal)


def register_circuit_tools(server: MCPServer[None], runtime: CollaborationRuntime, principal: PrincipalProvider) -> None:
    """Shared snapshots, target discovery and bounded atomic edit schemas."""
    @server.tool(annotations=READ_ONLY)
    @guard_handler
    async def list_projects(offset: int = 0) -> list[dict[str, object]]:
        """Discover saved projects explicitly shared with this verified AI client."""
        return await list_documents(runtime.database, await principal(), "project", offset)

    @server.tool(annotations=READ_ONLY)
    @guard_handler
    async def list_shared_workspaces(offset: int = 0) -> list[dict[str, object]]:
        """Discover explicitly shared tab snapshots; never assume an active tab."""
        return await list_documents(runtime.database, await principal(), "workspace", offset)

    @server.tool(annotations=READ_ONLY)
    @guard_handler
    async def get_circuit(document: UUID, revision: UUID | None = None) -> dict[str, object]:
        """Read graph/settings, revision, author, hash and acknowledgement boundary."""
        return await get_document(runtime.database, await principal(), document, revision)

    for alias in ("get_project", "get_workspace"):
        server.tool(name=alias, annotations=READ_ONLY)(get_circuit)

    @server.tool(annotations=READ_ONLY)
    @guard_handler
    async def validate_circuit(document: UUID, revision: UUID | None = None) -> dict[str, object]:
        """Check construction and solver readiness; return pin nodes and actionable diagnostics."""
        saved = await get_document(runtime.database, await principal(), document, revision)
        return {"document": str(document), "revision": saved["revision"],
                **inspect_contents(DocumentContents.model_validate(saved["contents"]))}

    server.tool(name="inspect_connectivity", annotations=READ_ONLY)(validate_circuit)
    register_edit_tools(server, runtime, principal)


def register_edit_tools(server: MCPServer[None], runtime: CollaborationRuntime, principal: PrincipalProvider) -> None:
    """Typed operation batches and validated replacements use one shared CAS service."""

    @server.tool(annotations=WRITE)
    @guard_handler
    async def apply_circuit_edits(document: UUID, command: EditDocument) -> dict[str, object]:
        """Apply one typed batch with expected_revision, idempotency_key and an undoable reason."""
        return await mutate_document(runtime.database, await principal(), document, command)

    @server.tool(annotations=WRITE)
    @guard_handler
    async def replace_circuit(document: UUID, command: ReplaceDocument) -> dict[str, object]:
        """Replace bounded validated graph/settings; no arbitrary SPICE, code or partial writes."""
        return await mutate_document(runtime.database, await principal(), document, command)


def register_history_tools(server: MCPServer[None], runtime: CollaborationRuntime, principal: PrincipalProvider) -> None:
    """Immutable history and non-destructive undo share the browser's CAS boundary."""
    @server.tool(name="list_revisions", annotations=READ_ONLY)
    @guard_handler
    async def revision_history(document: UUID, offset: int = 0) -> list[dict[str, object]]:
        """Read one bounded history page; offset allows older versions without unbounded output."""
        return await list_revisions(runtime.database, await principal(), document, offset)

    @server.tool(annotations=READ_ONLY)
    @guard_handler
    async def compare_revisions(document: UUID, before: UUID, after: UUID) -> dict[str, object]:
        """Compare two authorized revisions in the same circuit, not unrelated private projects."""
        actor = await principal()
        first = await get_document(runtime.database, actor, document, before)
        second = await get_document(runtime.database, actor, document, after)
        return compare_contents(DocumentContents.model_validate(first["contents"]),
                                DocumentContents.model_validate(second["contents"]))
    register_restore_tools(server, runtime, principal)


def register_restore_tools(server: MCPServer[None], runtime: CollaborationRuntime, principal: PrincipalProvider) -> None:
    """Restore, undo and export without deleting version history."""

    @server.tool(annotations=WRITE)
    @guard_handler
    async def undo_last_change(document: UUID, command: RevisionCommand) -> dict[str, object]:
        """Restore the immediate parent as a new revision, refusing intervening edits."""
        return await mutate_document(runtime.database, await principal(), document, command)

    @server.tool(annotations=WRITE)
    @guard_handler
    async def restore_revision(document: UUID, command: RestoreDocument) -> dict[str, object]:
        """Restore an explicit historical snapshot as a new audited head, never delete history."""
        return await mutate_document(runtime.database, await principal(), document, command)

    @server.tool(annotations=READ_ONLY)
    @guard_handler
    async def export_circuit(document: UUID, revision: UUID | None = None) -> dict[str, object]:
        """Export one authorized structured graph without credentials or executable model input."""
        return await get_document(runtime.database, await principal(), document, revision)


def register_run_tools(server: MCPServer[None], runtime: CollaborationRuntime, principal: PrincipalProvider) -> None:
    """Real durable solver jobs and bounded full-sample numerical evidence."""
    @server.tool(annotations=JOB)
    @guard_handler
    async def simulate_circuit(document: UUID, command: RunCommand) -> dict[str, object]:
        """Start a transient or AC job for an exact revision; poll get_simulation for completion."""
        return await start_run(runtime.jobs, await principal(), document, command)

    @server.tool(annotations=READ_ONLY)
    @guard_handler
    async def get_simulation(document: UUID, run: UUID) -> dict[str, object]:
        """Read durable status/provenance; fetch selected evidence with read_samples or measurements."""
        actor = await principal()
        saved = await get_run(runtime.database, actor, document, run)
        report = saved.pop("report")
        saved["signals"] = [trace.name for trace in (await get_report(runtime.database, actor, document, run)).traces] if report else []
        return saved

    @server.tool(annotations=READ_ONLY)
    @guard_handler
    async def list_simulations(document: UUID) -> list[dict[str, object]]:
        """Recover recent revision-bound run IDs after reconnecting; no implicit current run."""
        return await list_runs(runtime.database, await principal(), document)

    register_measurement_tools(server, runtime, principal)
    register_view_tools(server, runtime, principal)


def register_measurement_tools(server: MCPServer[None], runtime: CollaborationRuntime, principal: PrincipalProvider) -> None:
    """Full-sample unit-aware numeric evidence, with no arbitrary executable formulas."""

    @server.tool(annotations=READ_ONLY)
    @guard_handler
    async def read_samples(document: UUID, run: UUID, query: SampleQuery) -> dict[str, object]:
        """Read at most 256 actual complex/time samples, not decimated plot pixels."""
        return {"run": str(run), **sample_page(await get_report(runtime.database, await principal(), document, run), query)}

    @server.tool(annotations=READ_ONLY)
    @guard_handler
    async def measure_signals(document: UUID, run: UUID, query: MeasurementQuery) -> dict[str, object]:
        """Measure full solver samples in a physical time/frequency interval, with method and units."""
        return {"run": str(run), **measure(await get_report(runtime.database, await principal(), document, run), query)}

    @server.tool(annotations=READ_ONLY)
    @guard_handler
    async def evaluate_checks(document: UUID, run: UUID, check: IntentCheck) -> dict[str, object]:
        """Numerical pass/fail/unavailable evidence; never evaluate AI-provided formulas."""
        return {"run": str(run), **evaluate_check(await get_report(runtime.database, await principal(), document, run), check)}

    @server.tool(annotations=READ_ONLY)
    @guard_handler
    async def compare_simulations(document: UUID, before: UUID, after: UUID, query: MeasurementQuery) -> dict[str, object]:
        """Compare the same physical signal/window; keep different analyses and units explicit."""
        actor = await principal()
        first = measure(await get_report(runtime.database, actor, document, before), query)
        second = measure(await get_report(runtime.database, actor, document, after), query)
        return {"before": str(before), "after": str(after), "baseline": first, "changed": second,
                "compatible": first.get("analysis") == second.get("analysis") and first.get("unit") == second.get("unit"),
                "notice": "Compare actual sampled windows and excitation/settings before claiming improvement"}


def register_view_tools(server: MCPServer[None], runtime: CollaborationRuntime, principal: PrincipalProvider) -> None:
    """View commands require browser acknowledgement; export reads remain grant-protected."""

    @server.tool(annotations=JOB)
    @guard_handler
    async def set_observation_view(document: UUID, command: ObservationCommand) -> dict[str, object]:
        """Queue bounded highlight/seek for one current workspace; no autoplay or other-tab access."""
        return await set_view(runtime.database, await principal(), document, command)

    @server.tool(annotations=READ_ONLY)
    @guard_handler
    async def get_observation_status(document: UUID, command: UUID) -> dict[str, object]:
        """Confirm actual browser acknowledgement, or report a pending/expired view honestly."""
        return await view_status(runtime.database, await principal(), document, command)

    @server.tool(annotations=READ_ONLY)
    @guard_handler
    async def export_simulation(document: UUID, run: UUID) -> dict[str, object]:
        """Export the bounded complete authorized solver report and its immutable revision/provenance."""
        return await get_run(runtime.database, await principal(), document, run)


def register_resources(server: MCPServer[None], runtime: CollaborationRuntime, principal: PrincipalProvider) -> None:
    """Resource URIs confer no access; each read invokes the same grant checks as tools."""
    @server.resource("circuit-lab://circuits/{document}/{revision}", mime_type="application/json")
    async def circuit_resource(document: str, revision: str) -> str:
        try:
            saved = await get_document(runtime.database, await principal(), UUID(document), UUID(revision))
            return json.dumps(saved)
        except (ProjectFailure, ValidationError, ValueError) as failure:
            raise ResourceError("Circuit resource unavailable or not shared") from failure

    @server.resource("circuit-lab://runs/{document}/{run}", mime_type="application/json")
    async def run_resource(document: str, run: str) -> str:
        try:
            saved = await get_run(runtime.database, await principal(), UUID(document), UUID(run))
            saved.pop("report", None)
            return json.dumps(saved)
        except (ProjectFailure, ValidationError, ValueError) as failure:
            raise ResourceError("Simulation resource unavailable or not shared") from failure
