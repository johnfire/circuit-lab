"""Real-ngspice analog physics, graph safety and parser contracts."""

import math
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.schematic_engine import compile_schematic, read_frames, simulate_schematic
from backend.schematic_models import Part, SchematicRequest, Timing
from backend.schematic_topology import assign_nodes
from backend.simulation_engine import SimulationFailure
from backend.worker_gateway import launch_schematic


def test_real_rc_frames_share_clock_and_match_charge_equation(analog_request: SchematicRequest) -> None:
    report = launch_schematic(analog_request, "analog-physics")
    node = report.pin_nodes["C1:0"]
    traces = {trace.name: trace.values for trace in report.traces}
    index = min(range(len(report.times)), key=lambda i: abs(report.times[i] - .011))
    assert report.correlation_id == "analog-physics"
    assert len(report.times) == 301
    assert traces[f"V:{node}"][index] == pytest.approx(5 * (1 - math.exp(-1)), abs=.015)
    assert traces["I:R1"][index] == pytest.approx(traces["I:C1"][index], abs=1e-9)
    assert traces["I:V1"][index] == pytest.approx(-traces["I:R1"][index], abs=1e-9)
    assert all(len(trace.values) == len(report.times) for trace in report.traces)
    assert all(b - a == pytest.approx(.0001) for a, b in zip(report.times, report.times[1:]))


def test_dc_divider_and_inductor_branch_currents(analog_request: SchematicRequest) -> None:
    parts = [part.model_copy(update={"kind": "V", "pulse": None}) if part.id == "V1"
             else part.model_copy(update={"kind": "R", "value": 1000.0}) if part.id == "C1"
             else part for part in analog_request.parts]
    submitted = analog_request.model_copy(update={"parts": parts})
    report = simulate_schematic(submitted, "divider")
    traces = {trace.name: trace.values for trace in report.traces}
    assert traces[f"V:{report.pin_nodes['C1:0']}"][-1] == pytest.approx(2.5)
    assert traces["I:R1"][-1] == pytest.approx(.0025)
    parts[-2] = parts[-2].model_copy(update={"kind": "L", "value": .01})
    report = simulate_schematic(submitted.model_copy(update={"parts": parts}), "inductor")
    assert next(trace for trace in report.traces if trace.name == "I:C1").values[-1] == pytest.approx(.005)


@pytest.mark.parametrize("change, message", [
    ("missing_ground", "ground"), ("missing_wire", "every terminal"),
    ("duplicate_part", "unique"), ("duplicate_wire", "duplicate"),
    ("self_wire", "self-links"), ("invalid_pin", "missing terminal"),
    ("shorted", "shorted"), ("floating", "floating"),
])
def test_invalid_topology_rejected(analog_request: SchematicRequest, change: str, message: str) -> None:
    submitted = analog_request.model_dump()
    if change == "missing_ground":
        submitted["parts"][-1]["kind"] = "V"
    if change == "missing_wire":
        submitted["wires"] = submitted["wires"][:1]
    if change == "duplicate_part":
        submitted["parts"][1]["id"] = "V1"
    if change == "duplicate_wire":
        submitted["wires"].append(submitted["wires"][0])
    if change == "self_wire":
        submitted["wires"][0]["b"] = submitted["wires"][0]["a"]
    if change == "invalid_pin":
        submitted["wires"][0]["a"]["part"] = "nope"
    if change == "shorted":
        submitted["wires"].append({"a": {"part": "R1", "terminal": 0}, "b": {"part": "R1", "terminal": 1}})
    if change == "floating":
        submitted["parts"].extend([{"id": f"R{i}", "kind": "R", "value": 1000, "x": 4, "y": i} for i in (2, 3)])
        submitted["wires"].extend([{"a": {"part": "R2", "terminal": i}, "b": {"part": "R3", "terminal": i}} for i in (0, 1)])
    with pytest.raises(ValueError, match=message):
        assign_nodes(SchematicRequest.model_validate(submitted))


@pytest.mark.parametrize("value", ["1k\n.include /etc/passwd", float("inf"), float("nan"), True, 0, 1e20])
def test_component_values_cannot_inject_or_exceed_limits(value: object) -> None:
    with pytest.raises(ValidationError):
        Part.model_validate({"id": "R1", "kind": "R", "value": value, "x": 4, "y": 4})


@pytest.mark.parametrize("step", [1e-10, .1, .000001])
def test_time_budget_is_bounded(step: float) -> None:
    with pytest.raises(ValidationError):
        Timing(stop=.03, step=step)


def test_rotation_and_position_never_change_electrical_nodes(analog_request: SchematicRequest) -> None:
    moved = [part.model_copy(update={"x": 4, "y": 4, "rotation": 270}) for part in analog_request.parts]
    assert assign_nodes(analog_request.model_copy(update={"parts": moved})) == assign_nodes(analog_request)
    netlist, _, _ = compile_schematic(analog_request)
    assert "Vprobe" in netlist and "linearize" in netlist


@pytest.mark.parametrize("contents", ["", "0 NaN\n" * 11, "0 1 2\n" * 11, "invalid\n" * 11])
def test_malformed_solver_frames_fail_closed(tmp_path: Path, contents: str) -> None:
    frames = tmp_path / "frames.csv"
    frames.write_text(contents)
    with pytest.raises(SimulationFailure):
        read_frames(frames, ["V:n1"])


def test_missing_solver_frames_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(SimulationFailure):
        read_frames(tmp_path / "missing.csv", ["V:n1"])


def test_half_step_duration_uses_ngspice_frame_rounding(analog_request: SchematicRequest) -> None:
    submitted = analog_request.model_copy(update={"timing": Timing(stop=.00725, step=.0001)})
    report = launch_schematic(submitted, "half-step")
    assert len(report.times) == 74
