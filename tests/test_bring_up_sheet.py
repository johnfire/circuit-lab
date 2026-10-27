"""Bring-up checklists name the export's pads and nets and expect what the simulation measured."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.application import app
from backend.block_library import BLOCKS
from backend.bring_up_sheet import Reading, bring_up_sheet, describe, reading
from backend.schematic_engine import simulate_schematic
from backend.schematic_models import SchematicRequest
from backend.simulation_engine import SimulationFailure


def sheet_for(block_id: str, circuit: SchematicRequest | None = None) -> str:
    request = circuit or BLOCKS[block_id].circuit
    return bring_up_sheet(request, simulate_schematic(request, block_id))


def test_steady_nets_read_as_one_value_and_switching_ones_as_a_range() -> None:
    assert reading([0.0, 5.0, 5.0]) == Reading(final=5.0, low=0.0, high=5.0, average=10 / 3)
    assert describe(Reading(3.3, 3.29, 3.31, 3.3), "V") == "about 3.3V"
    assert describe(Reading(0.0, 0.0, 3.3, 1.65), "V") == "varies 0V to 3.3V; a DC meter shows about 1.65V"


def test_relay_driver_sheet_uses_export_pads_and_a_current_limited_supply() -> None:
    sheet = sheet_for("pi_relay_driver")
    assert "| /GPIO17 | RG pad 1 | varies 0V to 3.3V" in sheet
    assert "| /N1 | RC pad 1 | about 12V |" in sheet
    assert "- [ ] VS on J2 pin 1 (+): set 12V, current limit 50mA." in sheet
    assert "Q1 (IRLZ44N): tab/flat side" in sheet and "D1 (1N5819): cathode band" in sheet
    assert "RC: power at 70% of its 250mW limit" in sheet
    assert "P1:" not in sheet, "a 3.3 V pin near its 3.6 V maximum is headroom, not heat"
    assert "Board pins are driven by firmware" in sheet


def test_regulator_sheet_lists_electrolytic_polarity_and_regulated_output() -> None:
    sheet = sheet_for("lm1117_3v3_supply")
    assert "- [ ] C1: electrolytic, + to pad 1" in sheet and "- [ ] C2: electrolytic, + to pad 1" in sheet
    assert "| U1 pad 2 | about 3.3V |" in sheet
    assert "Open design issues" not in sheet


def test_unmet_support_rules_appear_as_open_issues() -> None:
    circuit = BLOCKS["lm1117_3v3_supply"].circuit.model_dump()
    for part in circuit["parts"]:
        if part["id"] == "C2":
            part["footprint"] = "c0805"
    sheet = sheet_for("ceramic", SchematicRequest.model_validate(circuit))
    assert "## 5. Open design issues" in sheet and "C2 is ceramic" in sheet


def test_bring_up_endpoint_simulates_audits_and_returns_markdown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setenv("CIRCUIT_AUDIT_PATH", str(audit_path))
    with TestClient(app, base_url="http://localhost") as client:
        response = client.post("/api/export/bring-up", json=BLOCKS["lm7805_5v_supply"].circuit.model_dump())
    assert response.status_code == 200
    assert response.json()["sheet"].startswith("# Bring-up checklist")
    entries = [json.loads(line) for line in audit_path.read_text().splitlines()]
    assert [(entry["target"], entry["outcome"]) for entry in entries] == [("bring_up", "started"), ("bring_up", "completed")]


def test_worker_outage_fails_only_the_bring_up_sheet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CIRCUIT_AUDIT_PATH", str(tmp_path / "audit.jsonl"))
    circuit = BLOCKS["lm7805_5v_supply"].circuit.model_dump()
    with TestClient(app, base_url="http://localhost") as client:
        with patch("backend.kicad_routes.launch_schematic", side_effect=SimulationFailure("worker busy")):
            assert client.post("/api/export/bring-up", json=circuit).status_code == 503
            assert client.post("/api/export/kicad", json=circuit).status_code == 200


def test_unwired_circuit_is_refused_before_any_simulation() -> None:
    circuit = BLOCKS["lm7805_5v_supply"].circuit.model_dump()
    circuit["wires"] = circuit["wires"][:2]
    with patch("backend.kicad_routes.launch_schematic") as launch:
        with TestClient(app, base_url="http://localhost") as client:
            response = client.post("/api/export/bring-up", json=circuit)
        launch.assert_not_called()
    assert response.status_code == 422 and "Not ready for a bring-up sheet" in response.text
