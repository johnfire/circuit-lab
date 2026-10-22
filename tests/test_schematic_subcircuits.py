"""Op-amps and linear regulators in real circuits: physics, rail limits and rating checks."""

import pytest

from backend.schematic_engine import simulate_schematic
from backend.schematic_models import SchematicResponse
from tests.test_schematic_devices import circuit, ratings_by_name


def final_voltage(report: SchematicResponse, pin: str) -> float:
    """Settled voltage at a part terminal."""
    node = report.pin_nodes[pin]
    return 0.0 if node == "0" else next(
        trace for trace in report.traces if trace.name == f"V:{node}").values[-1]


def regulator_circuit(device: str, input_voltage: float, load_ohms: float):
    """Input source → regulator → load resistor, ground pin to circuit ground."""
    return circuit([
        {"id": "VIN", "kind": "V", "value": input_voltage, "x": 4, "y": 10, "rotation": 90},
        {"id": "U1", "kind": "REG", "device": device, "value": 0, "x": 14, "y": 8},
        {"id": "RL", "kind": "R", "value": load_ohms, "x": 24, "y": 10, "rotation": 90},
        {"id": "G1", "kind": "GND", "value": 0, "x": 14, "y": 18},
    ], [("VIN", 0, "U1", 1), ("U1", 0, "RL", 0), ("U1", 2, "G1", 0), ("RL", 1, "G1", 0),
        ("VIN", 1, "G1", 0)], stop=0.001, step=1e-5)


def test_7805_regulates_and_its_power_check_catches_a_hot_linear_drop() -> None:
    light = simulate_schematic(regulator_circuit("lm7805", 12, 50), "reg-light")
    assert final_voltage(light, "U1:0") == pytest.approx(5.0, abs=0.01)
    assert all(check.passed for check in light.ratings)
    heavy = simulate_schematic(regulator_circuit("lm7805", 12, 10), "reg-heavy")
    stress = ratings_by_name(heavy)
    assert stress[("U1", "iout_max")] == pytest.approx(0.5, rel=0.01)
    assert stress[("U1", "pd_max")] == pytest.approx((12 - 5) * 0.5, rel=0.02)
    [power] = [check for check in heavy.ratings if check.rating == "pd_max"]
    assert not power.passed


def test_regulator_drops_out_when_headroom_is_missing() -> None:
    report = simulate_schematic(regulator_circuit("lm7805", 6, 50), "dropout")
    assert final_voltage(report, "U1:0") == pytest.approx(6 - 2.0, abs=0.02)


def test_lm317_divider_sets_its_output() -> None:
    report = simulate_schematic(circuit([
        {"id": "VIN", "kind": "V", "value": 12, "x": 4, "y": 10, "rotation": 90},
        {"id": "U1", "kind": "REG", "device": "lm317", "value": 0, "x": 14, "y": 8},
        {"id": "R1", "kind": "R", "value": 240, "x": 22, "y": 10, "rotation": 90},
        {"id": "R2", "kind": "R", "value": 720, "x": 22, "y": 16, "rotation": 90},
        {"id": "RL", "kind": "R", "value": 500, "x": 30, "y": 12, "rotation": 90},
        {"id": "G1", "kind": "GND", "value": 0, "x": 14, "y": 20},
    ], [("VIN", 0, "U1", 1), ("U1", 0, "R1", 0), ("R1", 1, "U1", 2), ("R1", 1, "R2", 0),
        ("R2", 1, "G1", 0), ("U1", 0, "RL", 0), ("RL", 1, "G1", 0), ("VIN", 1, "G1", 0)],
        stop=0.001, step=1e-5), "lm317")
    assert final_voltage(report, "U1:0") == pytest.approx(1.25 * (1 + 720 / 240) + 50e-6 * 720, abs=0.01)


def amplifier(device: str, supply: float, input_voltage: float):
    """Non-inverting gain-of-2 amplifier on a single supply, 10 kΩ feedback and load."""
    return circuit([
        {"id": "VS", "kind": "V", "value": supply, "x": 30, "y": 4, "rotation": 90},
        {"id": "VIN", "kind": "V", "value": input_voltage, "x": 4, "y": 12, "rotation": 90},
        {"id": "U1", "kind": "OPAMP", "device": device, "value": 0, "x": 16, "y": 10},
        {"id": "RF", "kind": "R", "value": 10000, "x": 22, "y": 16},
        {"id": "RG", "kind": "R", "value": 10000, "x": 12, "y": 18, "rotation": 90},
        {"id": "RL", "kind": "R", "value": 10000, "x": 28, "y": 12, "rotation": 90},
        {"id": "G1", "kind": "GND", "value": 0, "x": 16, "y": 21},
    ], [("VIN", 0, "U1", 1), ("U1", 0, "RF", 1), ("RF", 0, "U1", 2), ("U1", 2, "RG", 0),
        ("RG", 1, "G1", 0), ("U1", 0, "RL", 0), ("RL", 1, "G1", 0), ("VS", 0, "U1", 3),
        ("VS", 1, "G1", 0), ("U1", 4, "G1", 0), ("VIN", 1, "G1", 0)], stop=0.001, step=1e-5)


def test_opamp_amplifies_then_saturates_at_its_output_limit() -> None:
    linear = simulate_schematic(amplifier("mcp6002", 3.3, 1.0), "gain")
    assert final_voltage(linear, "U1:0") == pytest.approx(2.0, abs=0.01)
    assert all(check.passed for check in linear.ratings)
    saturated = simulate_schematic(amplifier("lm358", 5, 2.0), "rail")
    assert final_voltage(saturated, "U1:0") == pytest.approx(5 - 1.5, abs=0.06)


def test_opamp_supply_above_its_maximum_fails_the_rating_check() -> None:
    report = simulate_schematic(amplifier("mcp6002", 9, 1.0), "overvolt")
    [supply] = [check for check in report.ratings if check.rating == "vs_max"]
    assert not supply.passed and supply.measured == pytest.approx(9, abs=0.01)


def test_regulator_fed_opamp_starts_at_its_true_operating_point() -> None:
    parts = [part for part in amplifier("mcp6002", 3.3, 1.0).model_dump()["parts"] if part["id"] != "VS"]
    parts += [{"id": "VR", "kind": "V", "value": 5, "x": 4, "y": 4, "rotation": 90},
              {"id": "U2", "kind": "REG", "device": "lm1117_3v3", "value": 0, "x": 22, "y": 3}]
    wires = [(wire["a"]["part"], wire["a"]["terminal"], wire["b"]["part"], wire["b"]["terminal"])
             for wire in amplifier("mcp6002", 3.3, 1.0).model_dump()["wires"] if "VS" not in (
                 wire["a"]["part"], wire["b"]["part"])]
    wires += [("VR", 0, "U2", 1), ("U2", 2, "G1", 0), ("VR", 1, "G1", 0), ("U2", 0, "U1", 3)]
    report = simulate_schematic(circuit(parts, wires, stop=0.001, step=1e-5), "regulated-amp")
    output = next(trace for trace in report.traces if trace.name == "V:" + report.pin_nodes["U1:0"])
    assert output.values[0] == pytest.approx(2.0, abs=0.01), "DC operating point latched at the rail"
    assert output.values[-1] == pytest.approx(2.0, abs=0.01)
