"""Regression coverage for CLI failures and component substitutions."""

import argparse
import contextlib
import io
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from harness import run_circuit


def test_component_override_changes_resistor_value() -> None:
    netlist = "* RC\nR1 in out 10k\nC1 out 0 1u\n.end\n"
    edited = run_circuit.substitute_netlist(netlist, {"R1": "4700"})
    assert "R1 in out 4700" in edited
    assert "C1 out 0 1u" in edited


def test_unknown_override_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown"):
        run_circuit.substitute_netlist("R1 in out 10k\n", {"R2": "4700"})


def test_override_cannot_inject_control_commands() -> None:
    with pytest.raises(ValueError):
        run_circuit.substitute_netlist("R1 in out 10k\n", {"R1": "1k\nshell touch /tmp/no"})


def test_failed_simulation_returns_failed_cli_exit(tmp_path: Path) -> None:
    circuit_path = tmp_path / "broken.cir"
    circuit_path.write_text("* invalid\n.end\n")
    arguments = argparse.Namespace(file=str(circuit_path), set=None, sweep=None, plot=None, timeout=1)
    with patch.object(run_circuit, "run_ngspice", return_value=(1, "simulation failed", "")):
        with contextlib.redirect_stdout(io.StringIO()):
            assert run_circuit.cmd_run(arguments) == 1


def test_timeout_returns_failure_without_throwing(tmp_path: Path) -> None:
    with patch.object(run_circuit, "find_ngspice", return_value="ngspice"):
        with patch.object(subprocess, "run", side_effect=subprocess.TimeoutExpired("ngspice", 1)):
            status, transcript, _ = run_circuit.run_ngspice("* timeout\n.end", tmp_path, 1)
    assert status == -99
    assert transcript == "TIMEOUT"


def test_scaffold_contains_analysis_and_preserves_existing_files(tmp_path: Path) -> None:
    circuit_path = tmp_path / "starter.cir"
    run_circuit.cmd_new(str(circuit_path))
    assert "tran " in circuit_path.read_text()
    before = circuit_path.read_text()
    with pytest.raises(FileExistsError):
        run_circuit.cmd_new(str(circuit_path))
    assert circuit_path.read_text() == before


@pytest.mark.parametrize("output", ["0 NaN\n", "0 1 2\n", ""])
def test_cli_rejects_malformed_waveforms(tmp_path: Path, output: str) -> None:
    circuit_path = tmp_path / "bad_output.cir"
    circuit_path.write_text("* output test\n.end\n")
    arguments = argparse.Namespace(file=str(circuit_path), set=None, sweep=None, plot=None, timeout=1)

    def fake_simulator(_netlist: str, workdir: str, timeout: int) -> tuple[int, str, str]:
        (Path(workdir) / "v_out.csv").write_text(output)
        return 0, "", ""

    with patch.object(run_circuit, "run_ngspice", side_effect=fake_simulator):
        with contextlib.redirect_stdout(io.StringIO()):
            assert run_circuit.cmd_run(arguments) == 1


def test_cli_rejects_ignored_model_parameters(tmp_path: Path) -> None:
    circuit_path = tmp_path / "bad_model.cir"
    circuit_path.write_text("* model test\n.end\n")
    arguments = argparse.Namespace(file=str(circuit_path), set=None, sweep=None, plot=None, timeout=1)
    with patch.object(run_circuit, "run_ngspice", return_value=(0, "unrecognized parameter", "")):
        with contextlib.redirect_stdout(io.StringIO()):
            assert run_circuit.cmd_run(arguments) == 1
