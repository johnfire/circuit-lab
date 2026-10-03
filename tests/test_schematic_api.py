"""API validation, fail-closed auditing and real analog integration."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.application import app
from backend.schematic_models import SchematicRequest
from backend.simulation_engine import SimulationFailure


def test_real_analog_http_request_records_actor_and_correlated_outcomes(
    analog_request: SchematicRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setenv("CIRCUIT_AUDIT_PATH", str(audit_path))
    with TestClient(app, base_url="http://localhost") as client:
        response = client.post("/api/schematic/simulate", json=analog_request.model_dump())
    assert response.status_code == 200
    assert response.json()["correlation_id"] == response.headers["X-Correlation-ID"]
    entries = [json.loads(line) for line in audit_path.read_text().splitlines()]
    assert [entry["outcome"] for entry in entries] == ["started", "completed"]
    assert all(entry["actor"] == "user:local" for entry in entries)


@pytest.mark.parametrize("change", ["netlist", "value", "unwired", "pulse_budget"])
def test_invalid_graph_never_reaches_worker(analog_request: SchematicRequest, change: str) -> None:
    payload = analog_request.model_dump()
    if change == "netlist":
        payload["netlist"] = "shell whoami"
    elif change == "value":
        payload["parts"][1]["value"] = "1k\n.include /etc/passwd"
    elif change == "pulse_budget":
        payload["parts"][0]["pulse"] = {"period": 1e-6, "width": 5e-7, "delay": 0}
    else:
        payload["wires"] = payload["wires"][:1]
    with patch("backend.schematic_routes.launch_schematic") as launch:
        with TestClient(app, base_url="http://localhost") as client:
            assert client.post("/api/schematic/simulate", json=payload).status_code == 422
        launch.assert_not_called()


def test_worker_failure_does_not_break_catalog_or_next_analog_job(
    analog_request: SchematicRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CIRCUIT_AUDIT_PATH", str(tmp_path / "audit.jsonl"))
    with TestClient(app, base_url="http://localhost") as client:
        with patch("backend.schematic_routes.launch_schematic", side_effect=SimulationFailure("worker busy")):
            assert client.post("/api/schematic/simulate", json=analog_request.model_dump()).status_code == 503
        assert client.get("/api/health").status_code == 200
        assert len(client.get("/api/circuits").json()) == 9
        assert client.post("/api/schematic/simulate", json=analog_request.model_dump()).status_code == 200


def test_failed_audit_storage_prevents_analog_job(
    analog_request: SchematicRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CIRCUIT_AUDIT_PATH", str(tmp_path / "missing" / "audit.jsonl"))
    with patch("backend.schematic_routes.launch_schematic") as launch:
        with TestClient(app, base_url="http://localhost") as client:
            assert client.post("/api/schematic/simulate", json=analog_request.model_dump()).status_code == 503
        launch.assert_not_called()
