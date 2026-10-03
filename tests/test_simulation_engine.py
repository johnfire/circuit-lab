"""Real-engine regression tests for every example and verification boundary."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from backend.circuit_catalog import DESCRIPTIONS, list_circuits, parse_spice_number, read_components
from backend.simulation_engine import (
    SimulationFailure,
    prepare_simulation,
    read_waveforms,
    simulate,
    summarize_signal,
)
from backend.simulation_models import SimulationRequest


@pytest.mark.parametrize("circuit_id", list(DESCRIPTIONS))
def test_all_nine_examples_produce_valid_waveforms(circuit_id: str) -> None:
    report = simulate(circuit_id, SimulationRequest(), "regression")
    assert report.signals
    assert report.status == "passed"
    assert report.model_trust == "generic"
    assert all(signal.sample_count > 5 for signal in report.signals)
    assert all(check.passed for check in report.checks)


def test_catalog_does_not_parse_control_commands_as_components() -> None:
    circuit = next(circuit for circuit in list_circuits() if circuit.id == "voltage_divider")
    assert [component.name for component in circuit.components] == ["VIN", "R1", "R2"]
    assert read_components("R1 in out 10k\n.control\ndc VIN 0 5 1\n")[-1].name == "R1"


def test_resistor_override_changes_real_divider_output() -> None:
    report = simulate("voltage_divider", SimulationRequest(parameters={"R1": 4700}), "override")
    assert report.signals[0].final == pytest.approx(5 * 6800 / 11500, abs=0.001)
    assert "R1 in out 4700" in report.netlist


def test_adc_overvoltage_is_failed_check_not_success() -> None:
    report = simulate("voltage_divider", SimulationRequest(parameters={"R1": 1000}), "overvoltage")
    assert report.status == "failed"
    assert next(check for check in report.checks if "ADC" in check.name).passed is False


def test_rc_ripple_target_and_settling_are_measured() -> None:
    report = simulate("rc_lowpass", SimulationRequest(max_ripple_v=0.001), "ripple")
    assert report.status == "failed"
    assert next(check for check in report.checks if check.name == "Ripple meets target").passed is False
    unsettled = simulate("rc_lowpass", SimulationRequest(parameters={"R1": 100000}), "settling")
    assert unsettled.status == "failed"
    assert next(check for check in unsettled.checks if check.name == "Enough time to settle").passed is False


@pytest.mark.parametrize("parameters", [{"R9": 100}, {"R1": 0.001}, {"C1": 2}])
def test_unknown_or_out_of_bounds_values_are_rejected(parameters: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        prepare_simulation("rc_lowpass", SimulationRequest(parameters=parameters))


@pytest.mark.parametrize("value", [-1, 0, float("inf"), float("nan"), "1\nshell x"])
def test_non_numeric_or_non_finite_requests_are_rejected(value: object) -> None:
    with pytest.raises(ValidationError):
        SimulationRequest.model_validate({"parameters": {"R1": value}})


def test_raw_netlists_are_not_accepted() -> None:
    with pytest.raises(ValidationError):
        SimulationRequest.model_validate({"netlist": "shell x"})


def test_malformed_waveforms_fail_closed(tmp_path: Path) -> None:
    (tmp_path / "v_out.csv").write_text("0 1\n1 NaN\n")
    with pytest.raises(SimulationFailure, match="malformed"):
        read_waveforms(str(tmp_path))


def test_downsampling_preserves_narrow_spikes() -> None:
    rows = [(index * 0.001, 10.0 if index == 253 else 0.0) for index in range(10000)]
    signal = summarize_signal("v_out.csv", rows)
    assert (0.253, 10) in signal.points
    assert signal.maximum == 10
    assert len(signal.points) <= 1002
    assert signal.sample_count == 10000


def test_ngspice_ignored_model_parameters_are_failure(tmp_path: Path) -> None:
    with patch("backend.simulation_engine.run_ngspice", return_value=(0, "unrecognized parameter", "")):
        with pytest.raises(SimulationFailure, match="invalid model"):
            simulate("voltage_divider", SimulationRequest(), "warning")


def test_simulation_missing_binary_is_explicit_failure() -> None:
    with patch("harness.run_circuit.find_ngspice", return_value=""):
        with pytest.raises(RuntimeError, match="binary not found"):
            simulate("voltage_divider", SimulationRequest(), "missing")


@pytest.mark.parametrize("token,expected", [("10k", 10000), ("1u", 1e-6), ("2.2n", 2.2e-9)])
def test_spice_values_convert_to_si_units(token: str, expected: float) -> None:
    assert parse_spice_number(token) == pytest.approx(expected)


def test_export_roundtrip_preserves_waveforms_and_checks() -> None:
    report = simulate("voltage_divider", SimulationRequest(), "export")
    payload = json.loads(report.model_dump_json())
    assert payload["correlation_id"] == "export"
    assert len(payload["signals"][0]["points"]) == 11


def test_nand_checks_all_four_input_states() -> None:
    report = simulate("nand_xspice", SimulationRequest(), "truth-table")
    truth_table = next(check for check in report.checks if check.name == "NAND truth table")
    assert truth_table.passed
    assert "4/4" in truth_table.detail
