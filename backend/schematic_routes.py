"""Authenticated, audited API boundary for structured analog simulation."""

from typing import cast

from fastapi import APIRouter, HTTPException, Request

from backend.audit_log import record_simulation
from backend.schematic_ac_engine import compile_ac
from backend.schematic_ac_gateway import launch_ac
from backend.schematic_ac_models import ACRequest, ACResponse
from backend.schematic_engine import compile_schematic
from backend.schematic_models import SchematicRequest, SchematicResponse
from backend.simulation_engine import SimulationFailure
from backend.worker_gateway import launch_schematic

router = APIRouter()


@router.post("/api/schematic/ac", response_model=ACResponse)
def run_frequency_sweep(submitted: ACRequest, request: Request) -> ACResponse:
    """Validate, correlate and audit genuine small-signal AC simulation."""
    correlation_id = cast(str, request.state.correlation_id)
    actor = cast(str, request.state.actor)
    try:
        compile_ac(submitted)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    try:
        record_simulation("schematic_ac", correlation_id, "started", actor)
        report = launch_ac(submitted, correlation_id)
        record_simulation("schematic_ac", correlation_id, report.status, actor)
        return report
    except SimulationFailure as error:
        try:
            record_simulation("schematic_ac", correlation_id, "error", actor)
        except SimulationFailure:
            pass  # Audit storage failures already have their own logger.
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/api/schematic/simulate", response_model=SchematicResponse)
def run_analog(submitted: SchematicRequest, request: Request) -> SchematicResponse:
    """Validate the graph before accepting an audited isolated job."""
    correlation_id = cast(str, request.state.correlation_id)
    actor = cast(str, request.state.actor)
    try:
        compile_schematic(submitted)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    try:
        record_simulation("schematic", correlation_id, "started", actor)
        report = launch_schematic(submitted, correlation_id)
        record_simulation("schematic", correlation_id, report.status, actor)
        return report
    except SimulationFailure as error:
        try:
            record_simulation("schematic", correlation_id, "error", actor)
        except SimulationFailure:
            pass  # The audit writer already records its own storage failure.
        raise HTTPException(status_code=503, detail=str(error)) from error
