"""HTTP integration tests with real jobs, validation, tracing, and isolation."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.application import app
from backend.simulation_engine import SimulationFailure


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("CIRCUIT_AUDIT_PATH", str(tmp_path / "audit.jsonl"))
    return TestClient(app, base_url="http://localhost")


def test_health_and_catalog_do_not_require_simulator(client: TestClient) -> None:
    assert client.get("/api/health").json()["status"] == "ok"
    assert len(client.get("/api/circuits").json()) == 9


def test_api_runs_real_simulation_with_correlated_audit(
    client: TestClient, tmp_path: Path,
) -> None:
    response = client.post("/api/circuits/voltage_divider/simulate", json={"parameters": {"R1": 4700}})
    assert response.status_code == 200
    report = response.json()
    assert report["status"] == "passed"
    assert report["signals"][0]["final"] == pytest.approx(2.9565, abs=0.001)
    assert response.headers["X-Correlation-ID"] == report["correlation_id"]
    events = [json.loads(line) for line in (tmp_path / "audit.jsonl").read_text().splitlines()]
    assert [event["outcome"] for event in events] == ["started", "passed"]
    assert all(event["actor"] == "user:local" for event in events)
    assert all(event["correlation_id"] == report["correlation_id"] for event in events)


@pytest.mark.parametrize("payload", [
    {"netlist": "shell cat /etc/passwd"}, {"parameters": {"R1": "1k\nshell x"}},
    {"parameters": {"R99": 10}}, {"parameters": {"R1": 0}},
])
def test_invalid_requests_never_reach_worker(client: TestClient, payload: dict[str, object]) -> None:
    with patch("backend.application.launch_simulation") as worker:
        response = client.post("/api/circuits/voltage_divider/simulate", json=payload)
    assert response.status_code == 422
    worker.assert_not_called()


def test_unknown_circuit_is_not_a_filesystem_path(client: TestClient) -> None:
    response = client.post("/api/circuits/private_secret/simulate", json={})
    assert response.status_code == 404


def test_worker_failure_does_not_break_catalog_or_next_simulation(client: TestClient) -> None:
    with patch("backend.application.launch_simulation", side_effect=SimulationFailure("timed out")):
        assert client.post("/api/circuits/voltage_divider/simulate", json={}).status_code == 503
    assert client.get("/api/health").status_code == 200
    assert client.post("/api/circuits/voltage_divider/simulate", json={}).status_code == 200


def test_foreign_origin_and_rebinding_host_are_rejected(client: TestClient) -> None:
    assert client.post("/api/circuits/voltage_divider/simulate",
                       json={}, headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.get("/api/health", headers={"Host": "evil.example"}).status_code == 400


def test_large_payload_is_rejected(client: TestClient) -> None:
    response = client.post("/api/circuits/voltage_divider/simulate", content="x" * 9000)
    assert response.status_code == 413


def test_missing_audit_storage_rejects_job_without_breaking_health(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CIRCUIT_AUDIT_PATH", str(tmp_path / "missing" / "audit.jsonl"))
    with patch("backend.application.launch_simulation") as worker:
        response = client.post("/api/circuits/voltage_divider/simulate", json={})
    assert response.status_code == 503
    assert "audit is unavailable" in response.json()["detail"]
    worker.assert_not_called()
    assert client.get("/api/health").status_code == 200
