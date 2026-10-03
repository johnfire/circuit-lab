"""IPC unit and real-service integration tests for the container boundary."""

import socket
import struct
import subprocess
import sys
import time
from pathlib import Path
from threading import Thread
from unittest.mock import patch

import pytest

from backend.remote_worker import request_worker_simulation
from backend.schematic_models import SchematicRequest
from backend.simulation_engine import SimulationFailure
from backend.simulation_models import SimulationRequest
from backend.worker_gateway import launch_schematic
from backend.worker_protocol import MAX_REQUEST_BYTES, exchange_frame, receive_frame, send_frame
from backend.worker_service import SimulationHandler, SimulationServer, serve_worker


def test_json_frame_roundtrip() -> None:
    first, second = socket.socketpair()
    with first, second:
        send_frame(first, {"operation": "health"})
        assert receive_frame(second, MAX_REQUEST_BYTES) == {"operation": "health"}


def test_oversized_frame_is_rejected_before_body_allocation() -> None:
    first, second = socket.socketpair()
    with first, second:
        first.sendall(struct.pack("!I", MAX_REQUEST_BYTES + 1))
        with pytest.raises(ValueError, match="size limit"):
            receive_frame(second, MAX_REQUEST_BYTES)


def test_truncated_frame_fails_closed() -> None:
    first, second = socket.socketpair()
    with first, second:
        first.sendall(struct.pack("!I", 10) + b"{}")
        first.shutdown(socket.SHUT_WR)
        with pytest.raises(ValueError, match="closed"):
            receive_frame(second, MAX_REQUEST_BYTES)


@pytest.mark.parametrize("payload", [
    {"error": "worker is busy"}, {}, {"circuit_id": "wrong"},
])
def test_bad_remote_reports_fail_closed(payload: dict[str, object]) -> None:
    with patch("backend.remote_worker.exchange_frame", return_value=payload):
        with pytest.raises(SimulationFailure):
            request_worker_simulation("/unused.sock", "voltage_divider", SimulationRequest(), "ipc")


def test_remote_worker_unavailable_does_not_fall_back_to_local_execution() -> None:
    with pytest.raises(SimulationFailure, match="unavailable"):
        request_worker_simulation("/tmp/circuit-lab-nonexistent.sock", "voltage_divider",
                                  SimulationRequest(), "missing")


@pytest.fixture
def worker_socket(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    socket_path = str(tmp_path / "worker.sock")
    monkeypatch.setenv("CIRCUIT_WORKER_LISTEN", socket_path)
    with subprocess.Popen([sys.executable, "-m", "backend.worker_service"]) as service:
        for _ in range(100):
            if Path(socket_path).exists():
                break
            if service.poll() is not None:
                pytest.fail("Worker service exited before binding its socket")
            time.sleep(0.02)
        try:
            yield socket_path
        finally:
            service.terminate()
            service.wait(timeout=5)


def test_real_ipc_worker_health_simulation_and_invalid_job_recovery(worker_socket: str) -> None:
    assert exchange_frame(worker_socket, {"operation": "health"}) == {"status": "ok"}
    invalid = exchange_frame(worker_socket, {"circuit_id": "voltage_divider", "netlist": "shell x"})
    assert "error" in invalid
    report = request_worker_simulation(worker_socket, "voltage_divider",
                                      SimulationRequest(parameters={"R1": 4700}), "real-ipc")
    assert report.status == "passed"
    assert report.signals[0].final == pytest.approx(2.9565, abs=0.001)
    assert exchange_frame(worker_socket, {"operation": "health"}) == {"status": "ok"}


def test_in_process_server_handles_health_invalid_job_and_real_simulation(tmp_path: Path) -> None:
    socket_path = str(tmp_path / "in-process.sock")
    with SimulationServer(socket_path, SimulationHandler) as service:
        thread = Thread(target=service.serve_forever, daemon=True)
        thread.start()
        try:
            assert exchange_frame(socket_path, {"operation": "health"}) == {"status": "ok"}
            assert "error" in exchange_frame(socket_path, {"netlist": "shell x"})
            report = request_worker_simulation(socket_path, "voltage_divider",
                                               SimulationRequest(), "service-coverage")
            assert report.status == "passed"
        finally:
            service.shutdown()
            thread.join(timeout=5)


def test_service_does_not_replace_an_existing_regular_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    socket_path = tmp_path / "keep.txt"
    socket_path.write_text("must survive")
    monkeypatch.setenv("CIRCUIT_WORKER_LISTEN", str(socket_path))
    with pytest.raises(ValueError, match="non-socket"):
        serve_worker()
    assert socket_path.read_text() == "must survive"


def test_non_object_frame_is_rejected() -> None:
    first, second = socket.socketpair()
    with first, second:
        first.sendall(struct.pack("!I", 2) + b"[]")
        with pytest.raises(ValueError, match="object"):
            receive_frame(second, MAX_REQUEST_BYTES)


def test_real_analog_ipc_rejects_raw_netlists_and_recovers(
    worker_socket: str, analog_request: SchematicRequest, monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalid = {"operation": "schematic", "request": analog_request.model_dump(),
               "correlation_id": "analog-ipc", "netlist": "shell whoami"}
    assert "error" in exchange_frame(worker_socket, invalid)
    monkeypatch.setenv("CIRCUIT_WORKER_SOCKET", worker_socket)
    report = launch_schematic(analog_request, "analog-ipc")
    assert len(report.times) == 301
    assert report.correlation_id == "analog-ipc"
    assert "I:R1" in [trace.name for trace in report.traces]
    assert exchange_frame(worker_socket, {"operation": "health"}) == {"status": "ok"}
