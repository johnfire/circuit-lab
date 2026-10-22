"""Datasheet support capacitors are found on the wiring, with the ESR rule for picky regulators."""

import pytest
from pydantic import ValidationError

from backend.block_library import BLOCKS
from backend.part_library import LIBRARY
from backend.part_library_models import LibraryPart
from backend.project_inspection import inspect_contents
from backend.project_models import DocumentContents
from backend.schematic_models import SchematicRequest
from backend.schematic_topology import assign_nodes
from backend.support_checks import support_findings
from tests.test_schematic_devices import circuit

GROUND = {"id": "G1", "kind": "GND", "value": 0, "x": 16, "y": 20}


def regulator(device: str, output_capacitor: dict[str, object] | None) -> SchematicRequest:
    """A loaded regulator with an input capacitor, and optionally an output one."""
    parts = [{"id": "VIN", "kind": "V", "value": 5, "x": 4, "y": 8, "rotation": 90},
             {"id": "CI", "kind": "C", "value": 1e-5, "x": 9, "y": 11, "rotation": 90, "footprint": "radial"},
             {"id": "U1", "kind": "REG", "value": 0, "x": 14, "y": 8, "device": device},
             {"id": "RL", "kind": "R", "value": 100, "x": 24, "y": 11, "rotation": 90}, GROUND]
    connections = [("VIN", 0, "U1", 1), ("VIN", 0, "CI", 0), ("CI", 1, "G1", 0), ("U1", 2, "G1", 0),
                   ("U1", 0, "RL", 0), ("RL", 1, "G1", 0), ("VIN", 1, "G1", 0)]
    if output_capacitor is not None:
        parts.append({"id": "CO", "kind": "C", "x": 19, "y": 11, "rotation": 90, **output_capacitor})
        connections += [("U1", 0, "CO", 0), ("CO", 1, "G1", 0)]
    return circuit(parts, connections)


def findings(request: SchematicRequest) -> list[str]:
    return support_findings(request, assign_nodes(request))


def test_lm1117_needs_ten_microfarads_on_its_output() -> None:
    [missing] = findings(regulator("lm1117_3v3", None))
    assert missing.startswith("Required: U1 (LM1117-3.3) needs ≥ 10uF between OUT and GND/ADJ") and "Found none" in missing
    [small] = findings(regulator("lm1117_3v3", {"value": 4.7e-6, "footprint": "radial"}))
    assert "Found 4.7uF" in small
    assert findings(regulator("lm1117_3v3", {"value": 1e-5, "footprint": "radial"})) == []


def test_lm1117_rejects_a_ceramic_output_capacitor_but_mcp1700_accepts_one() -> None:
    [ceramic] = findings(regulator("lm1117_3v3", {"value": 1e-5, "footprint": "c1206"}))
    assert "CO is ceramic" in ceramic and "(datasheet p.15)" in ceramic
    assert findings(regulator("mcp1700_3v3", {"value": 1e-6, "footprint": "c0805"})) == []


def test_missing_input_capacitor_is_required_and_listed_before_recommendations() -> None:
    request = regulator("lm7805", None).model_dump()
    request["parts"] = [part for part in request["parts"] if part["id"] != "CI"]
    request["wires"] = [wire for wire in request["wires"] if "CI" not in (wire["a"]["part"], wire["b"]["part"])]
    found = findings(SchematicRequest.model_validate(request))
    assert [line.split(":")[0] for line in found] == ["Required", "Recommended"]
    assert "between IN and GND/ADJ" in found[0] and "between OUT and GND/ADJ" in found[1]


def test_single_supply_op_amp_only_needs_its_positive_rail_bypassed() -> None:
    block = BLOCKS["opamp_buffer_3v3"].circuit.model_dump()
    block["parts"] = [part for part in block["parts"] if part["id"] != "CB"]
    block["wires"] = [wire for wire in block["wires"] if "CB" not in (wire["a"]["part"], wire["b"]["part"])]
    [bypass] = findings(SchematicRequest.model_validate(block))
    assert bypass.startswith("Recommended: U1 (MCP6002) needs ≥ 10nF between V+ and ground")


@pytest.mark.parametrize("block_id", sorted(BLOCKS))
def test_every_library_block_meets_its_parts_support_rules(block_id: str) -> None:
    assert findings(BLOCKS[block_id].circuit) == []


def test_support_rules_must_name_real_terminals() -> None:
    part = LIBRARY["lm7805"].model_dump()
    part["support"][0]["between"] = ["drain", "GND"]
    with pytest.raises(ValidationError, match="Support rule must join"):
        LibraryPart.model_validate(part)


def test_a_verified_part_must_cite_pages_for_its_support_rules_too() -> None:
    part = LIBRARY["lm7805"].model_dump()
    part["trust"] = {"level": "verified", "reviewed_by": "test", "reviewed_on": "2026-10-22", "notes": ""}
    part["characterization"] = [{**test, "source": "datasheet p.5"} for test in part["characterization"]]
    part["support"][0]["source"] = "common practice"
    with pytest.raises(ValidationError, match="support rule"):
        LibraryPart.model_validate(part)


def test_validate_circuit_reports_design_checks_for_an_ai_client() -> None:
    unsafe = regulator("lm1117_3v3", {"value": 1e-5, "footprint": "c0805"})
    report = inspect_contents(DocumentContents.model_validate({"circuit": unsafe.model_dump()}))
    assert report["simulation_ready"] is True
    [check] = report["design_checks"]
    assert isinstance(check, str) and "CO is ceramic" in check
