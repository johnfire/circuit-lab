"""A bounded Unix-socket service for a no-network simulation container."""

import logging
import os
import socket
from pathlib import Path
from socketserver import BaseRequestHandler, ThreadingMixIn, UnixStreamServer
from threading import BoundedSemaphore
from typing import cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.schematic_ac_gateway import launch_ac
from backend.schematic_ac_models import ACJob
from backend.schematic_models import SchematicJob
from backend.simulation_engine import SimulationFailure
from backend.simulation_models import SimulationRequest
from backend.worker_gateway import launch_schematic, launch_simulation
from backend.worker_protocol import MAX_REQUEST_BYTES, receive_frame, send_frame

CONNECTION_SLOTS = BoundedSemaphore(2)
LOGGER = logging.getLogger("circuit-lab.worker")


class SimulationJob(BaseModel):
    """A curated recipe and values, not executable code or a raw netlist."""

    model_config = ConfigDict(extra="forbid")
    circuit_id: str = Field(max_length=64, pattern=r"^[a-z0-9_]+$")
    request: SimulationRequest
    correlation_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")


class SimulationHandler(BaseRequestHandler):
    """Validate one private IPC message and return a bounded report."""

    def handle(self) -> None:
        connection = cast(socket.socket, self.request)
        connection.settimeout(20)
        try:
            payload = receive_frame(connection, MAX_REQUEST_BYTES)
            if payload == {"operation": "health"}:
                send_frame(connection, {"status": "ok"})
                return
            if payload.get("operation") == "schematic_ac":
                ac_job = ACJob.model_validate(payload)
                send_frame(connection, launch_ac(ac_job.request, ac_job.correlation_id).model_dump())
                return
            if payload.get("operation") == "schematic":
                schematic = SchematicJob.model_validate(payload)
                send_frame(connection, launch_schematic(schematic.request, schematic.correlation_id).model_dump())
                return
            job = SimulationJob.model_validate(payload)
            report = launch_simulation(job.circuit_id, job.request, job.correlation_id)
            send_frame(connection, report.model_dump())
        except (OSError, ValueError, ValidationError, SimulationFailure) as error:
            LOGGER.warning("Worker job failed: %s", type(error).__name__)
            try:
                send_frame(connection, {"error": "Simulation failed or worker is busy. Please retry."})
            except (OSError, ValueError):
                LOGGER.warning("Worker response could not be delivered")


class SimulationServer(ThreadingMixIn, UnixStreamServer):
    """Reject surplus connections before spawning unbounded handler threads."""

    daemon_threads = True
    request_queue_size = 2

    def process_request(self, request: socket.socket | tuple[bytes, socket.socket],
                        client_address: str) -> None:
        """Enforce the shared two-job ceiling at the connection boundary."""
        if isinstance(request, tuple):
            self.shutdown_request(request[1])
            return
        if not CONNECTION_SLOTS.acquire(blocking=False):
            request.settimeout(1)
            try:
                send_frame(request, {"error": "Two simulations are already running. Please retry."})
            except (OSError, ValueError):
                LOGGER.warning("Busy worker response could not be delivered")
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except RuntimeError:
            CONNECTION_SLOTS.release()
            self.shutdown_request(request)
            raise

    def process_request_thread(self, request: socket.socket | tuple[bytes, socket.socket],
                               client_address: str) -> None:
        """Always release the job slot even if its handler fails."""
        try:
            super().process_request_thread(request, client_address)
        finally:
            CONNECTION_SLOTS.release()


def serve_worker() -> None:
    """Bind only IPC; the deployment gives this service no network namespace."""
    socket_path = Path(os.environ.get("CIRCUIT_WORKER_LISTEN", "/run/circuit-lab/worker.sock"))
    if socket_path.exists():
        if not socket_path.is_socket():
            raise ValueError("Refusing to replace a non-socket worker path")
        socket_path.unlink()
    os.umask(0o007)
    with SimulationServer(str(socket_path), SimulationHandler) as server:
        socket_path.chmod(0o660)
        server.serve_forever()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    serve_worker()
