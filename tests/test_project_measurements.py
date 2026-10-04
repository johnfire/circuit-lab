"""Measurement evidence uses genuine solver reports and never sampled plot reductions."""

import math

import pytest
from pydantic import ValidationError

from backend.project_measurements import (
    IntentCheck,
    MeasurementQuery,
    SampleQuery,
    SignalQuery,
    evaluate_check,
    measure,
    resolve_signal,
    sample_page,
    time_statistics,
)
from backend.project_models import ProjectFailure
from backend.schematic_ac_gateway import launch_ac
from backend.schematic_ac_models import ACRequest, Sweep
from backend.schematic_models import Pin, SchematicRequest, SchematicResponse
from backend.worker_gateway import launch_schematic


@pytest.fixture(scope="module")
def transient_report() -> SchematicResponse:
    graph = SchematicRequest.model_validate({"parts": [
        {"id": "V1", "kind": "V", "value": 5, "x": 6, "y": 8},
        {"id": "R1", "kind": "R", "value": 1000, "x": 16, "y": 6},
        {"id": "G1", "kind": "GND", "value": 0, "x": 16, "y": 16}],
        "wires": [
            {"a": {"part": "V1", "terminal": 0}, "b": {"part": "R1", "terminal": 0}},
            {"a": {"part": "R1", "terminal": 1}, "b": {"part": "G1", "terminal": 0}},
            {"a": {"part": "G1", "terminal": 0}, "b": {"part": "V1", "terminal": 1}}],
        "timing": {"stop": .01, "step": .001}})
    return launch_schematic(graph, "mcp-numerical-test")


def test_time_statistics_matches_browser_weighted_sine_oracle() -> None:
    times = [index / 1000 for index in range(401)]
    values = [2 + 5 * math.sin(2 * math.pi * 10 * time + math.pi / 4) for time in times]
    statistics = time_statistics(times, values)
    assert statistics["mean"] == pytest.approx(2, abs=1e-12)
    assert statistics["rms"] == pytest.approx(math.sqrt(16.5), abs=1e-12)
    assert statistics["ac_rms"] == pytest.approx(5 / math.sqrt(2), abs=1e-12)


@pytest.mark.parametrize("times,values", [
    ([], []), ([0], [1]), ([0, 1], [1]), ([0, 0], [1, 2]),
    ([1, 0], [1, 2]), ([0, float("inf")], [1, 2]), ([0, 1], [float("nan"), 2]),
])
def test_statistics_refuse_invalid_sample_arrays(times: list[float], values: list[float]) -> None:
    with pytest.raises(ProjectFailure, match="Statistics require"):
        time_statistics(times, values)


def test_real_ac_measurements_preserve_frequency_and_excitation_semantics(
    analog_request: SchematicRequest,
) -> None:
    cutoff = 1 / (2 * math.pi * .01)
    sweep = Sweep(source="V1", amplitude=2, phase=37, start=cutoff, stop=cutoff * 10,
                  spacing="log", points=10)
    report = launch_ac(ACRequest(circuit=analog_request, sweep=sweep), "mcp-ac-measurement")
    signal = SignalQuery(kind="differential", first=Pin(part="C1", terminal=0),
                         second=Pin(part="C1", terminal=1))
    query = MeasurementQuery(signal=signal, start=cutoff * .99, stop=cutoff * 10.01)
    measurement = measure(report, query)
    assert measurement["gain_maximum"] == pytest.approx(1 / math.sqrt(2), rel=1e-6)
    assert measurement["first_phase_degrees"] == pytest.approx(-45, abs=1e-6)
    assert measurement["axis_unit"] == "Hz"
    assert measurement["actual_window"] == [report.frequencies[0], report.frequencies[-1]]
    assert "rms" not in measurement
    page = sample_page(report, SampleQuery(signal=signal, limit=2))
    assert page["axis"] == report.frequencies[:2]
    assert page["imaginary"] is not None
    assert page["axis_unit"] == "Hz"
    assert evaluate_check(report, IntentCheck(query=query, metric="rms", unit="V",
                          comparison="less_equal", threshold=1))["status"] == "unavailable"


def test_real_current_and_signed_voltage_use_the_same_report(transient_report: SchematicResponse) -> None:
    query = SignalQuery(kind="differential", first=Pin(part="R1", terminal=0),
                        second=Pin(part="R1", terminal=1))
    unit, values, imaginary = resolve_signal(transient_report, query)
    assert unit == "V"
    assert values == pytest.approx([5] * 11)
    assert imaginary == [0] * 11
    current = SignalQuery(kind="current", first=Pin(part="R1", terminal=0))
    assert resolve_signal(transient_report, current)[1] == pytest.approx([.005] * 11)
    with pytest.raises(ProjectFailure, match="absent"):
        resolve_signal(transient_report, SignalQuery(kind="current", first=Pin(part="missing", terminal=0)))


def test_sample_pages_preserve_original_solver_values(transient_report: SchematicResponse) -> None:
    signal = SignalQuery(kind="node", first=Pin(part="R1", terminal=0))
    first = sample_page(transient_report, SampleQuery(signal=signal, offset=0, limit=3))
    assert first["axis"] == transient_report.times[:3]
    assert first["next_offset"] == 3
    assert first["decimated"] is False
    last = sample_page(transient_report, SampleQuery(signal=signal, offset=9, limit=3))
    assert last["next_offset"] is None
    assert len(last["axis"]) == 2


def test_deterministic_checks_and_unavailable_windows(transient_report: SchematicResponse) -> None:
    query = MeasurementQuery(signal=SignalQuery(kind="current", first=Pin(part="R1", terminal=0)),
                             start=0, stop=.01)
    measured = measure(transient_report, query)
    assert measured["mean"] == pytest.approx(.005)
    assert measured["ac_rms"] == pytest.approx(0, abs=1e-10)
    for limit, expected in ((.006, "pass"), (.004, "fail")):
        check = IntentCheck(query=query, metric="maximum", unit="A", comparison="less_equal", threshold=limit)
        assert evaluate_check(transient_report, check)["status"] == expected
    with pytest.raises(ProjectFailure, match="unit"):
        evaluate_check(transient_report, IntentCheck(query=query, metric="maximum", unit="V",
                       comparison="less_equal", threshold=5))
    query = query.model_copy(update={"start": .00001, "stop": .00002})
    assert measure(transient_report, query)["status"] == "unavailable"


@pytest.mark.parametrize("submitted", [
    {"signal": {"kind": "node", "first": {"part": "R1", "terminal": 0}}, "limit": 100000},
    {"signal": {"kind": "shell", "first": {"part": "R1", "terminal": 0}}},
    {"signal": {"kind": "node", "first": {"part": "R1", "terminal": 0}}, "expression": "exec(1)"},
])
def test_sample_queries_reject_executable_or_unbounded_inputs(submitted: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        SampleQuery.model_validate(submitted)
