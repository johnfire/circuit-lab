"""Reject mismatched frames and never bypass a failed remote worker."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, BoundedSemaphore, Event
from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from backend.schematic_engine import simulate_schematic
from backend.schematic_models import SchematicRequest, SchematicResponse
from backend.simulation_engine import SimulationFailure
from backend.simulation_models import SimulationRequest
from backend.worker_gateway import launch_schematic, launch_simulation


def test_remote_analog_failure_cannot_start_local_process(
    analog_request: SchematicRequest, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CIRCUIT_WORKER_SOCKET", "/tmp/circuit-lab-missing-analog.sock")
    with patch("backend.worker_gateway.subprocess.Popen") as process:
        with pytest.raises(SimulationFailure, match="unavailable"):
            launch_schematic(analog_request, "remote-only")
        process.assert_not_called()


@pytest.mark.parametrize("change", ["correlation", "nodes", "signals", "window"])
def test_wrong_remote_analog_report_is_rejected(
    analog_request: SchematicRequest, monkeypatch: pytest.MonkeyPatch, change: str,
) -> None:
    report = simulate_schematic(analog_request, "matched").model_dump()
    if change == "correlation":
        report["correlation_id"] = "different"
    elif change == "nodes":
        report["pin_nodes"]["R1:0"] = "wrong"
    elif change == "signals":
        report["traces"][0]["name"] = "V:wrong"
    else:
        report["times"] = report["times"][:-1]
        for trace in report["traces"]:
            trace["values"] = trace["values"][:-1]
    monkeypatch.setenv("CIRCUIT_WORKER_SOCKET", "/unused.sock")
    with patch("backend.worker_gateway.exchange_frame", return_value=report):
        with pytest.raises(SimulationFailure):
            launch_schematic(analog_request, "matched")


@pytest.mark.parametrize("change", ["nonuniform", "decreasing", "length", "duplicate", "start"])
def test_report_frames_require_one_uniform_shared_time_axis(analog_request: SchematicRequest, change: str) -> None:
    report = simulate_schematic(analog_request, "frames").model_dump()
    if change == "nonuniform":
        report["times"][2] += .00001
    elif change == "decreasing":
        report["times"][2] = -1
    elif change == "length":
        report["traces"][0]["values"].pop()
    elif change == "duplicate":
        report["traces"][1]["name"] = report["traces"][0]["name"]
    else:
        report["times"] = [time + .001 for time in report["times"]]
    with pytest.raises(ValidationError):
        SchematicResponse.model_validate(report)


def test_analog_solver_failure_is_bounded_and_explicit(analog_request: SchematicRequest) -> None:
    with patch("backend.schematic_engine.run_ngspice", return_value=(-99, "TIMEOUT", "")):
        with pytest.raises(SimulationFailure, match="failed to converge"):
            simulate_schematic(analog_request, "failed")


def test_analog_and_recipe_jobs_share_the_actual_two_slot_ceiling(analog_request: SchematicRequest) -> None:
    report = simulate_schematic(analog_request, "parallel").model_dump_json()
    started, finish = Barrier(3), Event()

    def communicate(payload: str, timeout: int) -> tuple[str, str]:
        started.wait(timeout=5)
        assert finish.wait(timeout=5)
        return report, ""

    process = Mock(returncode=0)
    process.__enter__ = Mock(return_value=process)
    process.__exit__ = Mock(return_value=False)
    process.communicate.side_effect = communicate
    with patch("backend.worker_gateway.WORKER_SLOTS", BoundedSemaphore(2)):
        with patch("backend.worker_gateway.subprocess.Popen", return_value=process) as launch:
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(launch_schematic, analog_request, "parallel") for _ in range(2)]
                try:
                    started.wait(timeout=5)
                    with pytest.raises(SimulationFailure, match="already running"):
                        launch_simulation("voltage_divider", SimulationRequest(), "third")
                    assert launch.call_count == 2
                finally:
                    finish.set()
                assert all(future.result(timeout=5).status == "completed" for future in futures)
