"""Real ngspice small-signal sweeps with strictly bounded complex output."""

import math
import tempfile
from pathlib import Path

from backend.schematic_ac_models import ACRequest, ACResponse, ComplexTrace
from backend.schematic_models import Part
from backend.schematic_topology import assign_nodes
from backend.simulation_engine import SimulationFailure
from harness.run_circuit import run_ngspice, simulation_error


def dc_bias(part: Part) -> float:
    """DC sources retain their value; sine retains offset; pulse starts low."""
    if part.sine:
        return part.sine.offset
    return part.value if part.kind == "V" else 0.0


def compile_ac(submitted: ACRequest) -> tuple[str, dict[str, str], list[str]]:
    """Generate every AC command and numeric source coefficient server-side."""
    nodes = assign_nodes(submitted.circuit)
    active = [(index, part) for index, part in enumerate(submitted.circuit.parts)
              if part.kind != "GND"]
    voltage_nodes = sorted(set(nodes.values()) - {"0"})
    vectors = [f"v({node})" for node in voltage_nodes] + [f"i(Vprobe{i})" for i, _ in active]
    names = [f"V:{node}" for node in voltage_nodes] + [f"I:{part.id}" for _, part in active]
    lines = ["Circuit Lab small-signal AC", ".options numdgt=12"]
    sweep = submitted.sweep
    for index, part in active:
        first, second = nodes[f"{part.id}:0"], nodes[f"{part.id}:1"]
        lines.append(f"Vprobe{index} {first} p{index} 0")
        if part.kind in {"V", "PULSE", "SIN"}:
            amplitude = sweep.amplitude if part.id == sweep.source else 0.0
            phase = sweep.phase if part.id == sweep.source else 0.0
            lines.append(f"V{index} p{index} {second} DC {dc_bias(part):.12g} "
                         f"AC {amplitude:.12g} {phase:.12g}")
        else:
            lines.append(f"{part.kind}{index} p{index} {second} {part.value:.12g}")
    spacing = "dec" if sweep.spacing == "log" else "lin"
    lines.extend([".control", "set wr_singlescale", "set numdgt=12",
                  f"ac {spacing} {sweep.points} {sweep.start:.12g} {sweep.stop:.12g}",
                  f"wrdata frequencies.csv {' '.join(vectors)}", "quit", ".endc", ".end"])
    return "\n".join(lines) + "\n", nodes, names


def read_complex_frames(path: Path, names: list[str]) -> tuple[list[float], list[ComplexTrace]]:
    """Parse the shared frequency column followed by real/imaginary pairs."""
    if not path.is_file() or path.stat().st_size > 4_000_000:
        raise SimulationFailure("AC output missing or exceeds its size limit")
    rows = path.read_text().splitlines()
    if not 2 <= len(rows) <= 1000:
        raise SimulationFailure("AC returned an unexpected number of frequency points")
    matrix: list[list[float]] = []
    try:
        for row in rows:
            coefficients = [float(coefficient) for coefficient in row.split()]
            if len(coefficients) != 1 + 2 * len(names) or not all(
                    math.isfinite(coefficient) for coefficient in coefficients):
                raise ValueError("Invalid complex frame")
            matrix.append(coefficients)
    except ValueError as error:
        raise SimulationFailure("AC returned malformed complex frames") from error
    traces = [ComplexTrace(name=name, unit="V" if name.startswith("V:") else "A",
                           real=[row[1 + 2 * index] for row in matrix],
                           imaginary=[row[2 + 2 * index] for row in matrix])
              for index, name in enumerate(names)]
    return [row[0] for row in matrix], traces


def simulate_ac(submitted: ACRequest, correlation_id: str) -> ACResponse:
    """Use the same bounded isolated ngspice execution as transient analysis."""
    netlist, nodes, names = compile_ac(submitted)
    with tempfile.TemporaryDirectory(prefix="circuit-lab-ac-") as workdir:
        status, transcript, stderr = run_ngspice(netlist, workdir, timeout=10)
        if simulation_error(status, transcript, stderr):
            raise SimulationFailure("AC solver failed. Check sources and connections.")
        frequencies, traces = read_complex_frames(Path(workdir) / "frequencies.csv", names)
    biases = {part.id: dc_bias(part) for part in submitted.circuit.parts
              if part.kind in {"V", "PULSE", "SIN"}}
    return ACResponse(correlation_id=correlation_id, frequencies=frequencies, traces=traces,
                      pin_nodes=nodes, excitation=submitted.sweep, dc_biases=biases, netlist=netlist,
                      warnings=["Small-signal AC about the DC operating point; not time playback.",
                                "Amplitudes are peak phasor magnitudes, phase relative to excitation.",
                                "Ideal analog components; not a hardware safety check."])
