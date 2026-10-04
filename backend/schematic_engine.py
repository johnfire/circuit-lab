"""Compile allow-listed analog graphs and export synchronous ngspice frames."""

import math
import tempfile
from pathlib import Path

from backend.schematic_models import Part, SchematicRequest, SchematicResponse, Trace
from backend.schematic_topology import assign_nodes
from backend.simulation_engine import SimulationFailure
from harness.run_circuit import run_ngspice, simulation_error


def component_lines(part: Part, index: int, nodes: dict[str, str], step: float) -> list[str]:
    """Insert a zero-volt series probe for signed terminal-0-to-1 current."""
    if part.kind == "GND":
        return []
    first, second = nodes[f"{part.id}:0"], nodes[f"{part.id}:1"]
    internal = f"p{index}"
    source = f"{part.value:.12g}"
    if part.pulse:
        pulse = part.pulse
        edge = min(step / 10, pulse.width / 10, (pulse.period - pulse.width) / 10)
        source = (f"PULSE(0 {source} {pulse.delay:.12g} {edge:.12g} {edge:.12g} "
                  f"{pulse.width:.12g} {pulse.period:.12g})")
    if part.sine:
        sine = part.sine
        source = (f"DC {sine.offset:.12g} SIN({sine.offset:.12g} {part.value:.12g} "
                  f"{sine.frequency:.12g} 0 0 {sine.phase:.12g})")
    prefix = "V" if part.kind in {"PULSE", "SIN"} else part.kind
    return [f"Vprobe{index} {first} {internal} 0", f"{prefix}{index} {internal} {second} {source}"]


def compile_schematic(submitted: SchematicRequest) -> tuple[str, dict[str, str], list[str]]:
    """Generate all executable syntax server-side, never from submitted text."""
    nodes = assign_nodes(submitted)
    voltage_nodes = sorted(set(nodes.values()) - {"0"})
    active = [(index, part) for index, part in enumerate(submitted.parts) if part.kind != "GND"]
    vectors = [f"v({node})" for node in voltage_nodes] + [f"i(Vprobe{i})" for i, _ in active]
    names = [f"V:{node}" for node in voltage_nodes] + [f"I:{part.id}" for _, part in active]
    timing = submitted.timing
    lines = ["Circuit Lab ideal analog schematic", ".options numdgt=12"]
    for index, part in enumerate(submitted.parts):
        lines.extend(component_lines(part, index, nodes, timing.step))
    lines.extend([".control", "set wr_singlescale", "set numdgt=12",
                  f"tran {timing.step:.12g} {timing.stop:.12g} 0 {timing.step / 10:.12g}",
                  f"linearize {' '.join(vectors)}", f"wrdata frames.csv {' '.join(vectors)}",
                  "quit", ".endc", ".end"])
    return "\n".join(lines) + "\n", nodes, names


def read_frames(path: Path, names: list[str]) -> tuple[list[float], list[Trace]]:
    """Read one bounded matrix, refusing partial, nonfinite or malformed output."""
    if not path.is_file() or path.stat().st_size > 4_000_000:
        raise SimulationFailure("Simulation produced no frames or exceeded its output limit")
    rows = path.read_text().splitlines()
    if not 11 <= len(rows) <= 2002:
        raise SimulationFailure("Simulation returned an unexpected number of frames")
    matrix: list[list[float]] = []
    try:
        for row in rows:
            values = [float(value) for value in row.split()]
            if len(values) != len(names) + 1 or not all(math.isfinite(value) for value in values):
                raise ValueError("Invalid frame")
            matrix.append(values)
    except ValueError as error:
        raise SimulationFailure("Simulation returned malformed frames") from error
    traces = [Trace(name=name, unit="V" if name.startswith("V:") else "A",
                    values=[row[index + 1] for row in matrix]) for index, name in enumerate(names)]
    return [row[0] for row in matrix], traces


def simulate_schematic(submitted: SchematicRequest, correlation_id: str) -> SchematicResponse:
    """Run an ideal analog graph under the existing isolated worker limits."""
    netlist, nodes, names = compile_schematic(submitted)
    with tempfile.TemporaryDirectory(prefix="circuit-lab-analog-") as workdir:
        status, transcript, stderr = run_ngspice(netlist, workdir, timeout=10)
        failure = simulation_error(status, transcript, stderr)
        if failure:
            raise SimulationFailure("Analog solver failed to converge. Check sources and connections.")
        times, traces = read_frames(Path(workdir) / "frames.csv", names)
    return SchematicResponse(correlation_id=correlation_id, times=times, traces=traces,
                             pin_nodes=nodes, netlist=netlist,
                             warnings=["Ideal R/C/L and sources only; no component ratings or Pi GPIO protection checks.",
                                       "Uniform frames are interpolated by ngspice; use a smaller interval for fast changes.",
                                       "Initial state is the DC operating point, not an uncharged capacitor."])
