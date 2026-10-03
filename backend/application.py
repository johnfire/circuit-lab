"""Local or trusted-proxy prototype API, with separately bounded simulations."""

import hashlib
import os
from collections.abc import Awaitable, Callable
from typing import cast
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response

from backend.account_export import export_account
from backend.audit_log import record_simulation
from backend.circuit_catalog import ROOT, Circuit, list_circuits, read_circuit
from backend.request_security import allowed_hosts, public_url, reject_unsafe_request
from backend.schematic_routes import router as schematic_router
from backend.simulation_engine import SimulationFailure, prepare_simulation
from backend.simulation_models import SimulationRequest, SimulationResponse
from backend.worker_gateway import launch_simulation

app = FastAPI(title="Circuit Lab", version="0.1.0", docs_url="/api/docs")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts())
app.include_router(schematic_router)


@app.middleware("http")
async def protect_local_requests(request: Request,
                                 call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """Reject foreign origins and oversized payloads; add per-request tracing."""
    request.state.correlation_id = str(uuid4())
    rejected = reject_unsafe_request(request)
    if rejected:
        return rejected
    if request.method == "POST" and len(await request.body()) > 8192:
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
def download_account(request: Request) -> JSONResponse:
    """Allow a signed-in person to download their own data."""
    return export_account(request)


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
