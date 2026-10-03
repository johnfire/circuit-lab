"""Unit tests for worker failures, process timeouts, and backpressure."""

import subprocess
from unittest.mock import Mock, patch

import pytest

from backend.simulation_engine import SimulationFailure
from backend.simulation_models import SimulationRequest
from backend.worker_gateway import launch_simulation


def worker_mock(stdout: str = "{}", returncode: int = 0) -> Mock:
    worker = Mock(returncode=returncode, pid=12345)
    worker.communicate.return_value = (stdout, "")
    worker.__enter__ = Mock(return_value=worker)
    worker.__exit__ = Mock(return_value=False)
    return worker


def test_invalid_worker_report_releases_slot_for_next_job() -> None:
    with patch("backend.worker_gateway.subprocess.Popen", return_value=worker_mock()):
        for _ in range(3):
            with pytest.raises(SimulationFailure, match="invalid report"):
                launch_simulation("voltage_divider", SimulationRequest(), "invalid")


def test_timeout_kills_entire_process_group() -> None:
    worker = worker_mock()
    worker.communicate.side_effect = [subprocess.TimeoutExpired("worker", 15), ("", "")]
    with patch("backend.worker_gateway.subprocess.Popen", return_value=worker):
        with patch("backend.worker_gateway.os.killpg") as kill_group:
            with pytest.raises(SimulationFailure, match="timed out"):
                launch_simulation("voltage_divider", SimulationRequest(), "timeout")
    kill_group.assert_called_once()
    assert kill_group.call_args.args[0] == 12345
    assert worker.communicate.call_count == 2


def test_busy_worker_limit_rejects_without_starting_process() -> None:
    with patch("backend.worker_gateway.WORKER_SLOTS") as slots:
        slots.acquire.return_value = False
        with patch("backend.worker_gateway.subprocess.Popen") as start:
            with pytest.raises(SimulationFailure, match="already running"):
                launch_simulation("voltage_divider", SimulationRequest(), "busy")
    start.assert_not_called()


def test_missing_worker_is_reported_and_releases_slot() -> None:
    with patch("backend.worker_gateway.subprocess.Popen", side_effect=OSError("missing")):
        with pytest.raises(SimulationFailure, match="unavailable"):
            launch_simulation("voltage_divider", SimulationRequest(), "missing")
