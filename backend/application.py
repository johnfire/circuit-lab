"""Local or trusted-proxy prototype API, with separately bounded simulations."""

import hashlib
import json
import logging
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import cast
from uuid import uuid4

import asyncpg
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response

from backend.account_export import export_account
from backend.audit_log import record_simulation
from backend.circuit_catalog import ROOT, Circuit, list_circuits, read_circuit
from backend.mcp_http import MCPResponse, create_authenticated_server, create_http_app
from backend.project_lifecycle import export_projects
from backend.project_models import ProjectFailure
from backend.project_routes import create_project_router
from backend.project_runtime import CollaborationRuntime
from backend.request_security import allowed_hosts, public_url, reject_unsafe_request
from backend.schematic_routes import router as schematic_router
from backend.simulation_engine import SimulationFailure, prepare_simulation
from backend.simulation_models import SimulationRequest, SimulationResponse
from backend.worker_gateway import launch_simulation

collaboration = CollaborationRuntime()
mcp_server = create_authenticated_server(collaboration)
mcp_http = create_http_app(mcp_server)


@asynccontextmanager
async def application_lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Own the mounted SDK session manager and independent application database jobs."""
    await collaboration.start()
    lifecycle_server = create_authenticated_server(collaboration)
    application.state.mcp_http = create_http_app(lifecycle_server)
    try:
        async with lifecycle_server.session_manager.run():
            yield
    finally:
        await collaboration.close()


app = FastAPI(title="Circuit Lab", version="0.2.0", docs_url="/api/docs", lifespan=application_lifespan)
app.state.mcp_http = mcp_http
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts())
app.include_router(schematic_router)
app.include_router(create_project_router(collaboration))


@app.exception_handler(ProjectFailure)
async def project_failure(request: Request, failure: ProjectFailure) -> JSONResponse:
    """Safe domain errors preserve the local browser draft and correlation evidence."""
    logging.getLogger("circuit-lab.collaboration").warning("Operation denied correlation=%s status=%s",
        getattr(request.state, "correlation_id", "unknown"), failure.status)
    return JSONResponse({"detail": failure.message}, status_code=failure.status)


@app.exception_handler(asyncpg.PostgresError)
async def project_storage_failure(request: Request, failure: asyncpg.PostgresError) -> JSONResponse:
    """A database outage fails one saved-circuit request without exposing SQL or submitted input."""
    logging.getLogger("circuit-lab.collaboration").error("Storage unavailable correlation=%s kind=%s",
        getattr(request.state, "correlation_id", "unknown"), type(failure).__name__)
    return JSONResponse({"detail": "Saved circuits unavailable. Your unsent draft remains local."}, status_code=503)


@app.api_route("/mcp", methods=["GET", "POST", "DELETE"], include_in_schema=False)
async def mcp_endpoint(request: Request) -> Response:
    """MCP has its own bearer boundary; never redirect native clients into browser login."""
    return MCPResponse(request.app.state.mcp_http)


@app.get("/.well-known/oauth-protected-resource/mcp", include_in_schema=False)
async def mcp_metadata(request: Request) -> Response:
    """Let clients discover the configured Keycloak issuer without granting circuit access."""
    return MCPResponse(request.app.state.mcp_http)


@app.middleware("http")
async def protect_local_requests(request: Request,
                                 call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """Reject foreign origins and oversized payloads; add per-request tracing."""
    request.state.correlation_id = str(uuid4())
    rejected = reject_unsafe_request(request)
    if rejected:
        return rejected
    is_mcp = request.url.path in {"/mcp", "/.well-known/oauth-protected-resource/mcp"}
    budget = 16384 if request.url.path.startswith("/api/projects") else 8192
    if not is_mcp and request.method in {"POST", "PUT", "PATCH"} and len(await request.body()) > budget:
        return JSONResponse({"detail": "Request too large"}, status_code=413)
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = request.state.correlation_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
    )
    return response


@app.get("/api/health")
def health() -> dict[str, str]:
    """Report service availability independently of simulation availability."""
    return {"status": "ok", "mode": "hosted-prototype" if public_url() else "local-prototype",
            "build_id": os.environ.get("CIRCUIT_BUILD_ID", "local")}


@app.get("/api/circuits", response_model=list[Circuit])
def catalog() -> list[Circuit]:
    """Expose the curated examples and their editable values."""
    return list_circuits()


@app.get("/api/account/export")
async def download_account(request: Request) -> JSONResponse:
    """Allow a signed-in person to download their own data."""
    response = export_account(request)
    if os.environ.get("CIRCUIT_DATABASE_URL") and collaboration.database.pool is None:
        raise ProjectFailure("Saved-circuit storage unavailable; account export is incomplete", 503)
    if collaboration.database.pool is not None:
        principal = await collaboration.browser(request)
        exported = await export_projects(collaboration.database, principal)
        profile_export = json.loads(bytes(response.body))
        profile_export["saved_projects"] = exported
        profile_export["note"] = "Current unsent browser drafts remain local; export those separately."
        return JSONResponse(profile_export, headers={key: value for key, value in response.headers.items()
                                                     if key != "content-length"})
    return response


@app.get("/api/session")
def browser_session(request: Request) -> JSONResponse:
    """Provide a noncredential storage namespace for the authenticated actor."""
    actor = cast(str, request.state.actor)
    return JSONResponse({"draft_scope": hashlib.sha256(actor.encode()).hexdigest()},
                        headers={"Cache-Control": "no-store"})


@app.get("/workbench")
def workbench_page() -> FileResponse:
    """Serve the protected workbench separately from the public landing page."""
    if not (frontend_path / 'index.html').is_file():
        raise HTTPException(status_code=503, detail='Workbench build unavailable')
    return FileResponse(frontend_path / 'index.html')


@app.post("/api/circuits/{circuit_id}/simulate", response_model=SimulationResponse)
def run_simulation(circuit_id: str, submitted: SimulationRequest,
                   request: Request) -> SimulationResponse:
    """Validate a recipe, isolate its job, and record its outcome."""
    correlation_id = cast(str, request.state.correlation_id)
    actor = cast(str, request.state.actor)
    try:
        read_circuit(circuit_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail="Unknown circuit") from error
    try:
        prepare_simulation(circuit_id, submitted)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    try:
        record_simulation(circuit_id, correlation_id, "started", actor)
        report = launch_simulation(circuit_id, submitted, correlation_id)
        record_simulation(circuit_id, correlation_id, report.status, actor)
    except SimulationFailure as error:
        try:
            record_simulation(circuit_id, correlation_id, "error", actor)
        except SimulationFailure:
            pass  # The audit writer already logs its own failure.
        raise HTTPException(status_code=503, detail=str(error)) from error
    return report


frontend_path = ROOT / "frontend" / "dist"
if frontend_path.is_dir():
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="workbench")
