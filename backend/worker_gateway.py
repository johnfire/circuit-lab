"""Timeout and concurrency boundary between HTTP and simulation processes."""

import json
import math
import os
import signal
import subprocess
import sys
from threading import BoundedSemaphore

from pydantic import ValidationError

from backend.circuit_catalog import ROOT
from backend.remote_worker import request_worker_simulation
from backend.schematic_engine import compile_schematic
from backend.schematic_models import SchematicRequest, SchematicResponse
from backend.simulation_engine import SimulationFailure
from backend.simulation_models import SimulationRequest, SimulationResponse
from backend.worker_protocol import exchange_frame

WORKER_SLOTS = BoundedSemaphore(2)


def launch_simulation(circuit_id: str, request: SimulationRequest,
                      correlation_id: str) -> SimulationResponse:
    """Run up to two isolated jobs; kill the process group on a timeout."""
    socket_path = os.environ.get("CIRCUIT_WORKER_SOCKET")
    if socket_path:
        return request_worker_simulation(socket_path, circuit_id, request, correlation_id)
    payload = json.dumps({"circuit_id": circuit_id, "request": request.model_dump(),
                          "correlation_id": correlation_id})
    try:
        return SimulationResponse.model_validate_json(run_payload(payload))
    except ValidationError as error:
        raise SimulationFailure("Simulation worker returned an invalid report") from error


def launch_schematic(request: SchematicRequest, correlation_id: str) -> SchematicResponse:
    """Use the same no-fallback isolation and job ceiling for analog graphs."""
    payload: dict[str, object] = {"operation": "schematic", "request": request.model_dump(),
               "correlation_id": correlation_id}
    try:
        socket_path = os.environ.get("CIRCUIT_WORKER_SOCKET")
        if socket_path:
            response = SchematicResponse.model_validate(exchange_frame(socket_path, payload))
        else:
            response = SchematicResponse.model_validate_json(run_payload(json.dumps(payload)))
        if response.correlation_id != correlation_id:
            raise SimulationFailure("Analog worker returned a mismatched report")
        _, expected_nodes, expected_names = compile_schematic(request)
        if response.pin_nodes != expected_nodes or [trace.name for trace in response.traces] != expected_names:
            raise SimulationFailure("Analog worker returned signals for a different circuit")
        if any(trace.unit != ("V" if trace.name.startswith("V:") else "A") for trace in response.traces):
            raise SimulationFailure("Analog worker returned mismatched signal units")
        if len(response.times) != math.floor(request.timing.stop / request.timing.step + 1.5):
            raise SimulationFailure("Analog worker returned an unexpected time window")
        if not math.isclose(response.times[1], request.timing.step, rel_tol=1e-6, abs_tol=1e-14):
            raise SimulationFailure("Analog worker returned an unexpected sample interval")
        return response
    except (OSError, ValueError, ValidationError) as error:
        raise SimulationFailure("Analog worker unavailable or returned an invalid report") from error


def run_payload(payload: str) -> str:
    """Bound one subprocess and release the shared slot on every exit path."""
    if not WORKER_SLOTS.acquire(blocking=False):
        raise SimulationFailure("Two simulations are already running. Please retry shortly.")
    try:
        with subprocess.Popen(
            [sys.executable, "-m", "backend.simulation_worker"], cwd=ROOT,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, start_new_session=True,
        ) as worker:
            try:
                stdout, _ = worker.communicate(payload, timeout=15)
            except subprocess.TimeoutExpired as error:
                os.killpg(worker.pid, signal.SIGKILL)
                worker.communicate()
                raise SimulationFailure("Simulation timed out") from error
            if worker.returncode != 0:
                raise SimulationFailure("Simulation failed. Review component values and retry.")
        return stdout
    except OSError as error:
        raise SimulationFailure("Simulation worker is unavailable") from error
    finally:
        WORKER_SLOTS.release()
