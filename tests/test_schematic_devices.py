"""Library devices in real circuits: physics, rating checks, AC, validation and tampering."""

from unittest.mock import patch

import pytest
from pydantic import ValidationError

from backend.schematic_ac_engine import simulate_ac
from backend.schematic_ac_models import ACRequest
from backend.schematic_engine import simulate_schematic
from backend.schematic_models import Part, SchematicRequest, SchematicResponse
from backend.schematic_topology import assign_nodes
from backend.simulation_engine import SimulationFailure
from backend.worker_gateway import launch_schematic

Connection = tuple[str, int, str, int]


def circuit(parts: list[dict[str, object]], connections: list[Connection],
            stop: float = 0.04, step: float = 2e-5) -> SchematicRequest:
    """Build a request from compact (part, terminal, part, terminal) connections."""
    wires = [{"a": {"part": a, "terminal": ta}, "b": {"part": b, "terminal": tb}}
             for a, ta, b, tb in connections]
    return SchematicRequest.model_validate({"parts": parts, "wires": wires,
                                            "timing": {"stop": stop, "step": step}})


def relay_driver(flyback: bool) -> SchematicRequest:
    """Benchmark 1: 3.3 V GPIO pulse → IRLZ44N → 12 V relay coil (400 Ω, 100 mH)."""
    parts: list[dict[str, object]] = [
        {"id": "VG", "kind": "PULSE", "value": 3.3, "x": 4, "y": 12, "rotation": 90,
         "pulse": {"period": 0.02, "width": 0.01, "delay": 0.001}},
        {"id": "RG", "kind": "R", "value": 100, "x": 10, "y": 10},
        {"id": "RPD", "kind": "R", "value": 100000, "x": 14, "y": 14, "rotation": 90},
        {"id": "Q1", "kind": "NMOS", "device": "irlz44n", "value": 0, "x": 20, "y": 12},
        {"id": "RC", "kind": "R", "value": 400, "x": 24, "y": 6, "rotation": 90},
        {"id": "LC", "kind": "L", "value": 0.1, "x": 24, "y": 9, "rotation": 90},
        {"id": "VS", "kind": "V", "value": 12, "x": 32, "y": 10, "rotation": 90},
        {"id": "G1", "kind": "GND", "value": 0, "x": 18, "y": 20},
    ]
    connections: list[Connection] = [
        ("VG", 0, "RG", 0), ("RG", 1, "Q1", 1), ("RPD", 0, "Q1", 1), ("RPD", 1, "G1", 0),
        ("Q1", 2, "G1", 0), ("VG", 1, "G1", 0), ("VS", 1, "G1", 0),
        ("VS", 0, "RC", 0), ("RC", 1, "LC", 0), ("LC", 1, "Q1", 0)]
    if flyback:
        parts.append({"id": "D1", "kind": "D", "device": "1n4148", "value": 0, "x": 28, "y": 8})
        connections += [("D1", 0, "Q1", 0), ("D1", 1, "VS", 0)]
    return circuit(parts, connections)


def ratings_by_name(report: SchematicResponse) -> dict[tuple[str, str], float]:
    """Measured stress keyed by (part, rating)."""
    return {(check.part, check.rating): check.measured for check in report.ratings}


def test_relay_with_flyback_switches_coil_and_passes_every_rating() -> None:
    report = simulate_schematic(relay_driver(flyback=True), "relay")
    stress = ratings_by_name(report)
    assert all(check.passed for check in report.ratings)
    assert stress[("Q1", "id_max")] == pytest.approx(12 / 400, rel=0.02)
    assert 12.3 < stress[("Q1", "vds_max")] < 13.2
    assert stress[("D1", "if_max")] == pytest.approx(12 / 400, rel=0.05)
    assert stress[("Q1", "pd_max")] < 1e-3
    assert {check.trust for check in report.ratings} == {"draft"}
    assert any("Draft parts (1n4148, irlz44n)" in warning for warning in report.warnings)


def test_relay_without_flyback_fails_on_the_inductive_spike_between_frames() -> None:
    report = simulate_schematic(relay_driver(flyback=False), "no-flyback")
    [vds] = [check for check in report.ratings if check.rating == "vds_max"]
    assert not vds.passed and vds.measured > 100
    frames_peak = max(max(trace.values) for trace in report.traces if trace.name.startswith("V:"))
    assert vds.measured > frames_peak, "peak must come from solver timepoints, not output frames"


def led_circuit(resistance: float) -> SchematicRequest:
    """3.3 V GPIO high → series resistor → red LED → ground."""
    return circuit([
        {"id": "V1", "kind": "V", "value": 3.3, "x": 6, "y": 10, "rotation": 90},
        {"id": "R1", "kind": "R", "value": resistance, "x": 14, "y": 8},
        {"id": "D1", "kind": "D", "device": "led_red_5mm", "value": 0, "x": 22, "y": 10,
         "rotation": 90},
        {"id": "G1", "kind": "GND", "value": 0, "x": 14, "y": 18},
    ], [("V1", 0, "R1", 0), ("R1", 1, "D1", 0), ("D1", 1, "G1", 0), ("G1", 0, "V1", 1)],
        stop=0.001, step=1e-5)


def test_led_current_limit_passes_with_68_ohms_and_fails_with_22() -> None:
    safe = simulate_schematic(led_circuit(68), "led-safe")
    current = next(trace for trace in safe.traces if trace.name == "I:D1").values[-1]
    assert current == pytest.approx((3.3 - 2.0) / 68, rel=0.1)
    assert all(check.passed for check in safe.ratings)
    overdriven = simulate_schematic(led_circuit(22), "led-hot")
    [forward] = [check for check in overdriven.ratings if check.rating == "if_max"]
    assert not forward.passed and forward.measured > 0.04


def test_bjt_switch_saturates_and_p_channel_high_side_conducts() -> None:
    bjt = simulate_schematic(circuit([
        {"id": "VB", "kind": "V", "value": 3.3, "x": 4, "y": 12, "rotation": 90},
        {"id": "RB", "kind": "R", "value": 1000, "x": 10, "y": 10},
        {"id": "Q1", "kind": "NPN", "device": "2n3904", "value": 0, "x": 18, "y": 12},
        {"id": "RL", "kind": "R", "value": 1000, "x": 22, "y": 6, "rotation": 90},
        {"id": "VC", "kind": "V", "value": 5, "x": 30, "y": 10, "rotation": 90},
        {"id": "G1", "kind": "GND", "value": 0, "x": 16, "y": 20},
    ], [("VB", 0, "RB", 0), ("RB", 1, "Q1", 1), ("Q1", 2, "G1", 0), ("VB", 1, "G1", 0),
        ("VC", 0, "RL", 0), ("RL", 1, "Q1", 0), ("VC", 1, "G1", 0)], stop=0.001, step=1e-5),
        "bjt")
    stress = ratings_by_name(bjt)
    assert stress[("Q1", "vceo_max")] < 5.01
    assert stress[("Q1", "ic_max")] == pytest.approx(4.9e-3, rel=0.05)
    pmos = simulate_schematic(circuit([
        {"id": "VS", "kind": "V", "value": 5, "x": 4, "y": 10, "rotation": 90},
        {"id": "Q1", "kind": "PMOS", "device": "ao3401a", "value": 0, "x": 14, "y": 8},
        {"id": "RL", "kind": "R", "value": 100, "x": 22, "y": 10, "rotation": 90},
        {"id": "G1", "kind": "GND", "value": 0, "x": 14, "y": 18},
    ], [("VS", 0, "Q1", 2), ("Q1", 1, "G1", 0), ("Q1", 0, "RL", 0), ("RL", 1, "G1", 0),
        ("VS", 1, "G1", 0)], stop=0.001, step=1e-5), "pmos")
    load = next(trace for trace in pmos.traces if trace.name == "I:RL").values[-1]
    assert load == pytest.approx(0.05, rel=0.02)
    assert all(check.passed for check in pmos.ratings)


def common_source(gate_bias: float) -> SchematicRequest:
    """BS170 with a 1 kΩ drain load from 12 V, gate driven by a DC source."""
    return circuit([
        {"id": "VIN", "kind": "V", "value": gate_bias, "x": 4, "y": 12, "rotation": 90},
        {"id": "Q1", "kind": "NMOS", "device": "bs170", "value": 0, "x": 14, "y": 12},
        {"id": "RD", "kind": "R", "value": 1000, "x": 18, "y": 6, "rotation": 90},
        {"id": "VDD", "kind": "V", "value": 12, "x": 26, "y": 10, "rotation": 90},
        {"id": "G1", "kind": "GND", "value": 0, "x": 12, "y": 20},
    ], [("VIN", 0, "Q1", 1), ("Q1", 2, "G1", 0), ("VIN", 1, "G1", 0), ("VDD", 0, "RD", 0),
        ("RD", 1, "Q1", 0), ("VDD", 1, "G1", 0)], stop=0.001, step=1e-5)


def settled_drain(gate_bias: float) -> float:
    """Final transient drain voltage at one DC gate bias."""
    report = simulate_schematic(common_source(gate_bias), "bias")
    return next(trace for trace in report.traces
                if trace.name == "V:" + report.pin_nodes["Q1:0"]).values[-1]


def test_ac_gain_of_a_saturated_mosfet_matches_its_dc_slope() -> None:
    bias, delta = 1.95, 1e-3
    assert 4 < settled_drain(bias) < 11, "bias must keep the transistor in saturation"
    dc_gain = (settled_drain(bias - delta) - settled_drain(bias + delta)) / (2 * delta)
    report = simulate_ac(ACRequest.model_validate({"circuit": common_source(bias).model_dump(),
        "sweep": {"source": "VIN", "amplitude": 0.01, "phase": 0, "start": 10, "stop": 1000,
                  "spacing": "log", "points": 5}}), "ac-amp")
    trace = next(trace for trace in report.traces if trace.name == "V:" + report.pin_nodes["Q1:0"])
    ac_gain = abs(complex(trace.real[0], trace.imaginary[0])) / 0.01
    assert dc_gain > 10
    assert ac_gain == pytest.approx(dc_gain, rel=0.03)
    assert ".model lib_bs170 VDMOS(" in report.netlist


@pytest.mark.parametrize("part, message", [
    ({"id": "D1", "kind": "D", "value": 0, "x": 4, "y": 4}, "library part"),
    ({"id": "R1", "kind": "R", "value": 100, "x": 4, "y": 4, "device": "1n4148"}, "library part"),
    ({"id": "D1", "kind": "D", "value": 0, "x": 4, "y": 4, "device": "nope"}, "Unknown library part"),
    ({"id": "Q1", "kind": "NPN", "value": 0, "x": 4, "y": 4, "device": "irlz44n"}, "is a NMOS"),
    ({"id": "Q1", "kind": "NMOS", "value": 1, "x": 4, "y": 4, "device": "irlz44n"}, "between 0"),
])
def test_device_fields_are_validated(part: dict[str, object], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        Part.model_validate(part)


def test_three_terminal_topology_rules() -> None:
    fet = {"id": "Q1", "kind": "NMOS", "device": "2n7000", "value": 0, "x": 14, "y": 10}
    source = {"id": "V1", "kind": "V", "value": 5, "x": 4, "y": 10, "rotation": 90}
    ground = {"id": "G1", "kind": "GND", "value": 0, "x": 14, "y": 18}
    diode_connected = circuit([source, fet, ground], [
        ("V1", 0, "Q1", 0), ("Q1", 0, "Q1", 1), ("Q1", 2, "G1", 0), ("V1", 1, "G1", 0)])
    assert assign_nodes(diode_connected)["Q1:0"] == assign_nodes(diode_connected)["Q1:1"]
    with pytest.raises(ValueError, match="shorted"):
        assign_nodes(circuit([source, fet, ground], [
            ("V1", 0, "G1", 0), ("Q1", 0, "G1", 0), ("Q1", 1, "G1", 0), ("Q1", 2, "G1", 0),
            ("V1", 1, "G1", 0)]))
    resistor = {"id": "R1", "kind": "R", "value": 100, "x": 14, "y": 10}
    with pytest.raises(ValueError, match="missing terminal"):
        assign_nodes(circuit([source, resistor, ground], [
            ("V1", 0, "R1", 2), ("R1", 0, "G1", 0), ("R1", 1, "G1", 0), ("V1", 1, "G1", 0)]))


def test_gateway_rejects_a_worker_that_drops_a_failing_rating() -> None:
    submitted = relay_driver(flyback=False)
    honest = simulate_schematic(submitted, "tamper")
    forged = honest.model_copy(update={"ratings": [check for check in honest.ratings if check.passed]})
    with patch("backend.worker_gateway.run_payload", return_value=forged.model_dump_json()):
        with pytest.raises(SimulationFailure, match="rating checks"):
            launch_schematic(submitted, "tamper")
