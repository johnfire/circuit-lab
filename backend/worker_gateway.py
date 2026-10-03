"""Timeout and concurrency boundary between HTTP and simulation processes."""

import json
import os
import signal
import subprocess
import sys
from threading import BoundedSemaphore

from pydantic import ValidationError

from backend.circuit_catalog import ROOT
from backend.remote_worker import request_worker_simulation
from backend.simulation_engine import SimulationFailure
from backend.simulation_models import SimulationRequest, SimulationResponse

WORKER_SLOTS = BoundedSemaphore(2)


def launch_simulation(circuit_id: str, request: SimulationRequest,
                      correlation_id: str) -> SimulationResponse:
    """Run up to two isolated jobs; kill the process group on a timeout."""
    socket_path = os.environ.get("CIRCUIT_WORKER_SOCKET")
    if socket_path:
        return request_worker_simulation(socket_path, circuit_id, request, correlation_id)
    if not WORKER_SLOTS.acquire(blocking=False):
        raise SimulationFailure("Two simulations are already running. Please retry shortly.")
    payload = json.dumps({"circuit_id": circuit_id, "request": request.model_dump(),
                          "correlation_id": correlation_id})
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
        return SimulationResponse.model_validate_json(stdout)
    except ValidationError as error:
        raise SimulationFailure("Simulation worker returned an invalid report") from error
    except OSError as error:
        raise SimulationFailure("Simulation worker is unavailable") from error
    finally:
        WORKER_SLOTS.release()
