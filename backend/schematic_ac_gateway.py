"""Verify AC identity and axes before accepting output from the isolated worker."""

import json
import math
import os

from pydantic import ValidationError

from backend.schematic_ac_engine import compile_ac, dc_bias
from backend.schematic_ac_models import ACRequest, ACResponse
from backend.simulation_engine import SimulationFailure
from backend.worker_gateway import run_payload
from backend.worker_protocol import exchange_frame


def launch_ac(request: ACRequest, correlation_id: str) -> ACResponse:
    """No local fallback when configured for remote isolation; same shared slots."""
    payload: dict[str, object] = {"operation": "schematic_ac", "request": request.model_dump(),
                                 "correlation_id": correlation_id}
    try:
        socket_path = os.environ.get("CIRCUIT_WORKER_SOCKET")
        if socket_path:
            report = ACResponse.model_validate(exchange_frame(socket_path, payload))
        else:
            report = ACResponse.model_validate_json(run_payload(json.dumps(payload)))
        verify_ac_report(request, report, correlation_id)
        return report
    except (OSError, ValueError, ValidationError) as error:
        raise SimulationFailure("AC worker unavailable or returned invalid output") from error


def verify_ac_report(request: ACRequest, report: ACResponse, correlation_id: str) -> None:
    """Refuse swapped circuits, excitation, units, bias or frequency windows."""
    _, nodes, names = compile_ac(request)
    biases = {part.id: dc_bias(part) for part in request.circuit.parts
              if part.kind in {"V", "PULSE", "SIN"}}
    if (report.correlation_id != correlation_id or report.pin_nodes != nodes or
            report.excitation != request.sweep or report.dc_biases != biases or
            [trace.name for trace in report.traces] != names or
            any(trace.unit != ("V" if trace.name.startswith("V:") else "A")
                for trace in report.traces)):
        raise SimulationFailure("AC worker returned a mismatched report")
    expected = request.sweep.frequencies()
    if len(expected) != len(report.frequencies) or any(
            not math.isclose(actual, predicted, rel_tol=1e-8, abs_tol=1e-12)
            for actual, predicted in zip(report.frequencies, expected)):
        raise SimulationFailure("AC worker returned an unexpected frequency axis")
