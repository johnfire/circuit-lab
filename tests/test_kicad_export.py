"""KiCad netlist and BOM export: pad maps, off-board connectors, footprint choices and safety."""

import csv
import io
import re

import pytest
from fastapi.testclient import TestClient

from backend.application import app
from backend.block_library import BLOCKS
from backend.footprint_catalog import GENERIC, verified_footprints
from backend.kicad_export import (
    HEADER_1X1,
    HEADER_1X2,
    PI_SOCKET,
    Component,
    export_kicad,
    netlist_text,
)
from backend.part_library import LIBRARY
from backend.schematic_models import SchematicRequest

NODE = re.compile(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)\)')


def nets(netlist: str) -> dict[str, set[tuple[str, str]]]:
    """Net name → {(ref, pad)} parsed from the exported netlist."""
    parsed = {}
    for line in netlist.splitlines():
        match = re.search(r'\(net \(code "\d+"\) \(name "([^"]+)"\)', line)
        if match:
            parsed[match.group(1)] = set(NODE.findall(line))
    return parsed


def net_of(netlist: str, ref: str, pad: str) -> set[tuple[str, str]]:
    """Everything connected to one pad."""
    return next(members for members in nets(netlist).values() if (ref, pad) in members)


def test_relay_driver_pads_land_on_the_right_nets() -> None:
    exported = export_kicad(BLOCKS["pi_relay_driver"].circuit)
    netlist = exported.netlist
    assert netlist.count("(") == netlist.count(")")
    assert ("RG", "2") in net_of(netlist, "Q1", "1"), "IRLZ44N gate (TO-220 pad 1) meets the gate resistor"
    assert ("D1", "2") in net_of(netlist, "Q1", "2"), "drain (pad 2) meets the flyback diode's anode"
    assert ("J2", "6") in net_of(netlist, "Q1", "3"), "source (pad 3) is ground, like every Pi GND pin"
    assert ("J1", "1") in net_of(netlist, "D1", "1"), "the diode's cathode goes to the +12 V input"
    assert ("J2", "11") in nets(netlist)["/GPIO17"], "GPIO17 is physical header pin 11"
    assert f'(footprint "{PI_SOCKET}")' in netlist and f'(footprint "{HEADER_1X2}")' in netlist
    assert any("No LCSC part number" in warning for warning in exported.warnings)


def test_bom_groups_identical_parts_in_jlc_columns() -> None:
    rows = list(csv.reader(io.StringIO(export_kicad(BLOCKS["opamp_noninverting_gain"].circuit).bom_csv)))
    assert rows[0] == ["Comment", "Designator", "Footprint", "LCSC Part #"]
    resistors = next(row for row in rows if row[0] == "10k")
    assert set(resistors[1].split(",")) == {"RF", "RG", "RL"}
    assert next(row for row in rows if row[0] == "MCP6002")[2] == "DIP-8_W7.62mm"


def test_footprint_choice_changes_package_and_pads_stay_correct() -> None:
    circuit = BLOCKS["pi_relay_driver"].circuit.model_dump()
    for part in circuit["parts"]:
        if part["id"] == "D1":
            part["footprint"] = "sma"
        if part["kind"] == "R":
            part["footprint"] = "r0805"
    netlist = export_kicad(SchematicRequest.model_validate(circuit)).netlist
    assert '(ref "D1") (value "1N5819") (footprint "Diode_SMD:D_SMA")' in netlist
    assert netlist.count("Resistor_SMD:R_0805_2012Metric") == 3
    assert ("D1", "2") in net_of(netlist, "Q1", "2")


def test_non_pi_boards_become_labelled_wire_pads_with_ground() -> None:
    circuit = BLOCKS["pi_gpio_led"].circuit.model_dump()
    circuit["parts"][0]["board_pin"] = {"board": "arduino_uno_r3", "pin": "D13", "mode": "output_high"}
    exported = export_kicad(SchematicRequest.model_validate(circuit))
    assert '(value "Arduino Uno R3 D13") (footprint "' + HEADER_1X1 + '")' in exported.netlist
    assert '(value "Arduino Uno R3 GND")' in exported.netlist
    assert any("single wire pads" in warning for warning in exported.warnings)


def test_every_exportable_footprint_was_checked_against_kicads_library() -> None:
    used = {footprint.kicad for part in LIBRARY.values() for footprint in part.footprints}
    used |= {option.kicad for options in GENERIC.values() for option in options}
    used |= {HEADER_1X1, HEADER_1X2, PI_SOCKET}
    assert used - verified_footprints() == set()


def test_http_export_refuses_incomplete_wiring_and_returns_files() -> None:
    with TestClient(app, base_url="http://localhost") as client:
        good = client.post("/api/export/kicad", json=BLOCKS["lm7805_5v_supply"].circuit.model_dump())
        unwired = BLOCKS["lm7805_5v_supply"].circuit.model_dump()
        unwired["wires"] = unwired["wires"][:3]
        bad = client.post("/api/export/kicad", json=unwired)
    assert good.status_code == 200
    assert good.json()["netlist"].startswith('(export (version "E")')
    assert bad.status_code == 422 and "Not ready for PCB export" in bad.text


@pytest.mark.parametrize("block_id", sorted(BLOCKS))
def test_every_library_block_exports(block_id: str) -> None:
    exported = export_kicad(BLOCKS[block_id].circuit)
    assert exported.netlist.count("(") == exported.netlist.count(")")
    assert '"/GND"' in exported.netlist


def test_lcsc_numbers_are_written_the_way_kicad_writes_component_fields() -> None:
    netlist = netlist_text([Component("R1", "10k", "Resistor_SMD:R_0805_2012Metric", "C17414",
                                      [("1", "0"), ("2", "n1")])], {"0": "GND", "n1": "N1"})
    assert '(fields (field (name "LCSC") "C17414")) (property (name "LCSC") (value "C17414"))' in netlist
    assert '(net (code "1") (name "/GND") (node (ref "R1") (pin "1")))' in netlist
