"""Curated netlist execution and trustworthy result parsing."""

import math
import tempfile
import time
from pathlib import Path

from backend.circuit_catalog import read_circuit, read_netlist
from backend.simulation_models import Check, Signal, SimulationRequest, SimulationResponse
from backend.verification_checks import Waveforms, evaluate_intent
from harness.run_circuit import read_wrdata_2col, run_ngspice, simulation_error, substitute_netlist


class SimulationFailure(RuntimeError):
    """A single simulation failed without invalidating other jobs."""


def prepare_simulation(circuit_id: str, request: SimulationRequest) -> tuple[str, dict[str, float]]:
    """Validate editable values against their declared catalog limits."""
    circuit = read_circuit(circuit_id)
    allowed = {parameter.name: parameter for parameter in circuit.parameters}
    values = {name: parameter.value for name, parameter in allowed.items()}
    for name, value in request.parameters.items():
        if name not in allowed:
            raise ValueError(f"Unknown editable component: {name}")
        parameter = allowed[name]
        if not parameter.minimum <= value <= parameter.maximum:
            raise ValueError(f"{name} must be between {parameter.minimum:g} and {parameter.maximum:g} {parameter.unit}")
        values[name] = value
    overrides = {name: f"{value:.12g}" for name, value in values.items()}
    return substitute_netlist(read_netlist(circuit_id), overrides), values


def read_waveforms(workdir: str) -> Waveforms:
    """Reject malformed, empty, or non-finite simulator output."""
    waveforms = {}
    for signal_path in sorted(Path(workdir).glob("*.csv")):
        if signal_path.stat().st_size > 16_000_000:
            raise SimulationFailure("Simulation output exceeded its size limit")
        _, rows = read_wrdata_2col(signal_path)
        raw_count = len(signal_path.read_text().splitlines())
        if not rows or raw_count != len(rows):
            raise SimulationFailure("Simulation produced malformed or empty samples")
        waveforms[signal_path.name] = rows
    if not waveforms:
        raise SimulationFailure("Simulation produced no waveforms")
    return waveforms


def summarize_signal(name: str, rows: list[tuple[float, float]]) -> Signal:
    """Preserve extrema from every chart bucket, and full-resolution statistics."""
    bucket_size = max(1, math.ceil(len(rows) / 500))
    chart_points = []
    for start in range(0, len(rows), bucket_size):
        bucket = rows[start:start + bucket_size]
        extrema = sorted({min(bucket, key=lambda point: point[1]),
                          max(bucket, key=lambda point: point[1])})
        chart_points.extend(extrema)
    chart_points = sorted(set([rows[0], *chart_points, rows[-1]]))
    voltages = [voltage for _, voltage in rows]
    return Signal(name=name.removesuffix(".csv"), points=chart_points,
                  minimum=min(voltages), maximum=max(voltages), final=voltages[-1],
                  sample_count=len(rows))


def simulate(circuit_id: str, request: SimulationRequest,
             correlation_id: str) -> SimulationResponse:
    """Run an example, evaluate actual samples, and state the model limitations."""
    started = time.monotonic()
    netlist, values = prepare_simulation(circuit_id, request)
    with tempfile.TemporaryDirectory(prefix="circuit-lab-") as workdir:
        status, transcript, stderr = run_ngspice(netlist, workdir, timeout=10)
        error_detail = simulation_error(status, transcript, stderr)
        if error_detail:
            raise SimulationFailure(error_detail)
        waveforms = read_waveforms(workdir)
    checks = [Check(name="Simulation completed", passed=True,
                    detail="ngspice returned successfully with finite waveform samples.")]
    checks.extend(evaluate_intent(circuit_id, values, waveforms, request.max_ripple_v))
    return SimulationResponse(
        circuit_id=circuit_id, correlation_id=correlation_id,
        status="passed" if all(check.passed for check in checks) else "failed",
        parameters=values, signals=[summarize_signal(name, rows) for name, rows in waveforms.items()],
        checks=checks, netlist=netlist, duration_ms=round((time.monotonic() - started) * 1000, 2),
        warnings=["Generic/ideal models. These checks do not verify real component ratings or hardware safety."],
    )
