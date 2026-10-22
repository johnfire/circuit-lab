"""Run each library part's declared characterization tests on real ngspice."""

import re
import tempfile
from pathlib import Path

from backend.model_primitives import StrictModel
from backend.part_library import model_card, model_name
from backend.part_library_models import (
    BjtCurrentGain,
    BjtSaturationVoltage,
    Characterization,
    DiodeForwardVoltage,
    LibraryPart,
    MosfetOnResistance,
    MosfetThreshold,
    ZenerVoltage,
)
from harness.run_circuit import run_ngspice, simulation_error

PRINTED_VALUE = re.compile(r"^(?P<name>[a-z_]+)\s*=\s*(?P<value>[-+0-9.eE]+)\s*$", re.MULTILINE)
GAIN_SWEEP_POINTS = 2000


class CharacterizationResult(StrictModel):
    """One measured specification, compared with its stated bounds."""

    part: str
    test: str
    measured: float | None
    unit: str
    min: float | None
    max: float | None
    passed: bool
    detail: str


def device_line(part: LibraryPart, terminals: str) -> str:
    """Instantiate a library device on generated nodes; prefix letters follow SPICE."""
    prefix = {"D": "D", "NMOS": "M", "PMOS": "M", "NPN": "Q", "PNP": "Q"}[part.kind]
    return f"{prefix}1 {terminals} {model_name(part)}"


def operating_point_netlist(part: LibraryPart, lines: list[str], expression: str) -> str:
    """Solve one DC operating point and print a single derived quantity."""
    return "\n".join([f"Characterize {part.id}", model_card(part), *lines, ".control", "op",
                      f"let measured = {expression}", "print measured", "quit", ".endc",
                      ".end"]) + "\n"


def diode_netlist(part: LibraryPart, test: DiodeForwardVoltage | ZenerVoltage) -> str:
    """Force forward current into the anode, or reverse current into the cathode."""
    if isinstance(test, DiodeForwardVoltage):
        lines = [f"I1 0 a {test.current:.12g}", device_line(part, "a 0")]
        return operating_point_netlist(part, lines, "v(a)")
    lines = [f"I1 0 k {test.current:.12g}", device_line(part, "0 k")]
    return operating_point_netlist(part, lines, "v(k)")


def mosfet_netlist(part: LibraryPart, test: MosfetThreshold | MosfetOnResistance) -> str:
    """Measure magnitudes so N- and P-channel parts share one test definition."""
    sign = -1 if part.kind == "PMOS" else 1
    if isinstance(test, MosfetThreshold):
        lines = [f"I1 0 d {sign * test.drain_current:.12g}", device_line(part, "d d 0")]
        return operating_point_netlist(part, lines, "abs(v(d))")
    lines = [f"VG g 0 {sign * test.gate_voltage:.12g}",
             f"I1 0 d {sign * test.drain_current:.12g}", device_line(part, "d g 0")]
    return operating_point_netlist(part, lines, f"abs(v(d)) / {test.drain_current:.12g}")


def saturation_netlist(part: LibraryPart, test: BjtSaturationVoltage) -> str:
    """Force both collector and base currents; the collector settles at Vce(sat)."""
    sign = -1 if part.kind == "PNP" else 1
    lines = [f"IB 0 b {sign * test.base_current:.12g}",
             f"IC 0 c {sign * test.collector_current:.12g}", device_line(part, "c b 0")]
    return operating_point_netlist(part, lines, "abs(v(c))")


def gain_netlist(part: LibraryPart, test: BjtCurrentGain) -> str:
    """Sweep base current at fixed Vce and record collector current for interpolation."""
    sign = -1 if part.kind == "PNP" else 1
    stop = test.collector_current / 10
    return "\n".join([
        f"Characterize {part.id}", model_card(part), f"VCE c 0 {sign * test.collector_voltage:.12g}",
        "IB 0 b 0", device_line(part, "c b 0"), ".control", "set wr_singlescale",
        f"dc IB 0 {sign * stop:.12g} {sign * stop / GAIN_SWEEP_POINTS:.12g}",
        "let collector = abs(i(VCE))", "wrdata gain.csv collector", "quit", ".endc", ".end",
    ]) + "\n"


def printed_measurement(transcript: str) -> float | None:
    """Read the single `measured = value` line, or nothing if the solver printed none."""
    values = [float(match["value"]) for match in PRINTED_VALUE.finditer(transcript)
              if match["name"] == "measured"]
    return values[-1] if values else None


def interpolated_gain(path: Path, test: BjtCurrentGain) -> float | None:
    """Find the base current that produces the target collector current; return Ic/Ib."""
    if not path.is_file():
        return None
    rows = [[abs(float(cell)) for cell in row.split()] for row in path.read_text().splitlines()]
    for (base_low, collector_low), (base_high, collector_high) in zip(rows, rows[1:]):
        if collector_low <= test.collector_current <= collector_high and collector_high > collector_low:
            fraction = (test.collector_current - collector_low) / (collector_high - collector_low)
            base = base_low + fraction * (base_high - base_low)
            return test.collector_current / base if base > 0 else None
    return None


def netlist_for(part: LibraryPart, test: Characterization) -> tuple[str, str]:
    """The generated netlist and the measured quantity's unit."""
    match test:
        case DiodeForwardVoltage() | ZenerVoltage():
            return diode_netlist(part, test), "V"
        case MosfetThreshold():
            return mosfet_netlist(part, test), "V"
        case MosfetOnResistance():
            return mosfet_netlist(part, test), "ohm"
        case BjtSaturationVoltage():
            return saturation_netlist(part, test), "V"
        case BjtCurrentGain():
            return gain_netlist(part, test), "hFE"


def run_test(part: LibraryPart, test: Characterization) -> CharacterizationResult:
    """Simulate one test in its own temporary directory and judge it against its bounds."""
    netlist, unit = netlist_for(part, test)
    with tempfile.TemporaryDirectory(prefix="circuit-lab-part-") as workdir:
        status, transcript, stderr = run_ngspice(netlist, workdir, timeout=20)
        failure = simulation_error(status, transcript, stderr)
        measured = None if failure else (
            interpolated_gain(Path(workdir) / "gain.csv", test) if isinstance(test, BjtCurrentGain)
            else printed_measurement(transcript))
    within = measured is not None and (test.min is None or measured >= test.min) and (
        test.max is None or measured <= test.max)
    detail = failure or ("no measurement produced" if measured is None
                         else "within stated bounds" if within else "outside stated bounds")
    return CharacterizationResult(part=part.id, test=test.test, measured=measured, unit=unit,
                                  min=test.min, max=test.max, passed=within, detail=detail)


def characterize(part: LibraryPart) -> list[CharacterizationResult]:
    """Run every declared test; one failing test never hides the others."""
    return [run_test(part, test) for test in part.characterization]
