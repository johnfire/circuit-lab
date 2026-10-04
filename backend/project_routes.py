"""Authenticated browser APIs calling the same revision/grant/run services as MCP."""

from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.project_documents import (
    create_document,
    get_document,
    list_documents,
    list_revisions,
    mutate_document,
)
from backend.project_grants import create_grant, list_grants, revoke_grants
from backend.project_lifecycle import export_projects
from backend.project_models import NewDocument, NewGrant, ReplaceDocument, RevisionCommand
from backend.project_runs import RunCommand, get_run, list_runs, start_run
from backend.project_runtime import CollaborationRuntime
from backend.project_views import acknowledge_view, pending_view


def create_project_router(runtime: CollaborationRuntime) -> APIRouter:
    """Register bounded authenticated actions without duplicating service authorization."""
    router = APIRouter(prefix="/api/projects", tags=["Saved circuits"])
    register_document_routes(router, runtime)
    register_sharing_routes(router, runtime)
    register_evidence_routes(router, runtime)
    return router


def register_document_routes(router: APIRouter, runtime: CollaborationRuntime) -> None:
    """Private saved projects and independently acknowledged browser workspaces."""
    @router.get("/status")
    async def status() -> dict[str, object]:
        return {"enabled": runtime.database.pool is not None and runtime.identity_ready,
                "clients": sorted(runtime.verifier.approved_clients), "endpoint": runtime.verifier.resource,
                "manual_tokens": False}

    @router.get("")
    async def catalog(request: Request, kind: str = "project", offset: int = 0) -> list[dict[str, object]]:
        return await list_documents(runtime.database, await runtime.browser(request), kind, offset)

    @router.post("")
    async def create(request: Request, command: NewDocument) -> dict[str, object]:
        return await create_document(runtime.database, await runtime.browser(request), command)

    @router.get("/export")
    async def export(request: Request) -> JSONResponse:
        contents = await export_projects(runtime.database, await runtime.browser(request))
        return JSONResponse(contents, headers={"Content-Disposition": 'attachment; filename="circuit-lab-projects.json"',
                                               "Cache-Control": "no-store"})

    @router.get("/{document}")
    async def read(request: Request, document: UUID, revision: UUID | None = None) -> dict[str, object]:
        return await get_document(runtime.database, await runtime.browser(request), document, revision)

    @router.post("/{document}/replace")
    async def replace(request: Request, document: UUID, command: ReplaceDocument) -> dict[str, object]:
        return await mutate_document(runtime.database, await runtime.browser(request), document, command)

    @router.post("/{document}/undo")
    async def undo(request: Request, document: UUID, command: RevisionCommand) -> dict[str, object]:
        return await mutate_document(runtime.database, await runtime.browser(request), document, command)

    @router.get("/{document}/history")
    async def history(request: Request, document: UUID, offset: int = 0) -> list[dict[str, object]]:
        return await list_revisions(runtime.database, await runtime.browser(request), document, offset)


def register_sharing_routes(router: APIRouter, runtime: CollaborationRuntime) -> None:
    """No sharing mutation is exposed as an AI circuit-edit tool."""
    @router.get("/{document}/grants")
    async def grants(request: Request, document: UUID) -> list[dict[str, object]]:
        return await list_grants(runtime.database, await runtime.browser(request), document)

    @router.post("/{document}/grants")
    async def share(request: Request, document: UUID, command: NewGrant) -> dict[str, object]:
        return await create_grant(runtime.database, await runtime.browser(request), document, command,
                                  runtime.verifier.approved_clients)

    @router.post("/{document}/stop-sharing")
    async def stop(request: Request, document: UUID) -> dict[str, object]:
        return await revoke_grants(runtime.database, await runtime.browser(request), document)


def register_evidence_routes(router: APIRouter, runtime: CollaborationRuntime) -> None:
    """Runs and live observation acknowledgement remain target- and revision-bound."""
    @router.post("/{document}/runs")
    async def simulate(request: Request, document: UUID, command: RunCommand) -> dict[str, object]:
        return await start_run(runtime.jobs, await runtime.browser(request), document, command)

    @router.get("/{document}/runs")
    async def runs(request: Request, document: UUID) -> list[dict[str, object]]:
        return await list_runs(runtime.database, await runtime.browser(request), document)

    @router.get("/{document}/runs/{run}")
    async def report(request: Request, document: UUID, run: UUID) -> dict[str, object]:
        return await get_run(runtime.database, await runtime.browser(request), document, run)

    @router.get("/{document}/view")
    async def view(request: Request, document: UUID) -> dict[str, object] | None:
        return await pending_view(runtime.database, await runtime.browser(request), document)

    @router.post("/{document}/view/{command}/acknowledge")
    async def acknowledge(request: Request, document: UUID, command: UUID) -> dict[str, object]:
        return await acknowledge_view(runtime.database, await runtime.browser(request), document, command)
