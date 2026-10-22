"""Measure every library device's and board pin's stress on the solver's own timepoints.

Peaks are taken by ngspice `meas` on the raw transient solution, before resampling to output
frames, so a spike shorter than the frame interval is still caught.
"""

import re
from dataclasses import dataclass
from typing import Literal

from backend.part_library import LIBRARY
from backend.part_library_models import Rating
from backend.passive_ratings import CHOSEN_ON_PART, passive_limits, positive
from backend.schematic_models import Part, RatingCheck, SchematicRequest
from backend.schematic_pins import pin_of
from backend.simulation_engine import SimulationFailure

PRINTED_RATING = re.compile(r"^(?P<name>rating\d+)\s*=\s*(?P<value>[-+0-9.eE]+)\s*$", re.MULTILINE)
AVERAGED_RATINGS = frozenset({"pd_max", "power_max"})


@dataclass(frozen=True)
class RatingProbe:
    """One generated measurement: which rating, how it is reduced, and its SPICE expression."""

    name: str
    part: Part
    device: str
    rating: str
    limit: Rating
    trust: Literal["draft", "verified"]
    statistic: Literal["peak", "average"]
    expression: str


def stress_expressions(kind: str, v: list[str], current: str) -> dict[str, str]:
    """SPICE vector expressions for each rating a device family can have.

    `current` flows into terminal 0: anode, drain, collector, or the op-amp/regulator output.
    """
    if kind == "D":
        return {"if_max": positive(current), "vr_max": positive(f"{v[1]}-{v[0]}"),
                "iz_max": positive(f"-{current}"), "pd_max": f"abs(({v[0]}-{v[1]})*{current})"}
    if kind in {"NMOS", "PMOS"}:
        return {"vds_max": f"abs({v[0]}-{v[2]})", "vgs_max": f"abs({v[1]}-{v[2]})",
                "id_max": f"abs({current})", "pd_max": f"abs(({v[0]}-{v[2]})*{current})"}
    if kind in {"NPN", "PNP"}:
        return {"vceo_max": f"abs({v[0]}-{v[2]})", "ic_max": f"abs({current})",
                "pd_max": f"abs(({v[0]}-{v[2]})*{current})"}
    if kind == "OPAMP":
        return {"vs_max": f"abs({v[3]}-{v[4]})", "iout_max": f"abs({current})"}
    return {"vin_max": f"abs({v[1]}-{v[2]})", "iout_max": f"abs({current})",
            "pd_max": f"abs(({v[1]}-{v[0]})*{current})"}


def pin_stress(part: Part, voltage: str, current: str) -> tuple[str, str, dict[str, tuple[Rating, str]]]:
    """A board pin's limits and expressions: pin current and voltage, or a supply's budget."""
    board, header_pin = pin_of(part)
    if header_pin.current_max is not None:
        return board.id, board.trust.level, {
            "supply_current_max": (header_pin.current_max, f"abs({current})")}
    ratings = board.electrical.ratings
    return board.id, board.trust.level, {
        "pin_current_max": (ratings["pin_current_max"], f"abs({current})"),
        "pin_voltage_max": (ratings["pin_voltage_max"], positive(voltage)),
        "pin_negative_voltage_max": (ratings["pin_negative_voltage_max"], positive(f"-{voltage}"))}


def part_limits(part: Part, index: int, nodes: dict[str, str]
                ) -> tuple[str, str, dict[str, tuple[Rating, str]]] | None:
    """(device id, trust, {rating: (limit, expression)}) for a rated part, or None."""
    voltages = ["0" if node == "0" else f"v({node})" for node in
                (nodes[pin] for pin in sorted(pin for pin in nodes if pin.startswith(f"{part.id}:")))]
    current = f"i(Vprobe{index})"
    if part.kind == "PIN":
        return pin_stress(part, voltages[0], current)
    if part.device is None:
        return passive_limits(part, voltages, current)
    library_part = LIBRARY[part.device]
    expressions = stress_expressions(part.kind, voltages, current)
    return library_part.id, library_part.trust.level, {
        name: (rating, expressions[name]) for name, rating in library_part.ratings.items()}


def rating_probes(submitted: SchematicRequest, nodes: dict[str, str]) -> list[RatingProbe]:
    """Every rating of every library device, board pin, resistor and capacitor, in a stable order."""
    probes: list[RatingProbe] = []
    for index, part in enumerate(submitted.parts):
        limits = part_limits(part, index, nodes)
        if limits is None:
            continue
        device, trust, ratings = limits
        for rating, (limit, expression) in sorted(ratings.items()):
            probes.append(RatingProbe(name=f"rating{len(probes)}", part=part, device=device,
                                      rating=rating, limit=limit,
                                      trust="verified" if trust == "verified" or limit.source == CHOSEN_ON_PART
                                      else "draft",
                                      statistic="average" if rating in AVERAGED_RATINGS else "peak",
                                      expression=expression))
    return probes


def rating_control_lines(probes: list[RatingProbe]) -> list[str]:
    """Commands to run right after `tran` and before `linearize` replaces the raw solution."""
    lines: list[str] = []
    for probe in probes:
        reduction = "AVG" if probe.statistic == "average" else "MAX"
        lines += [f"let {probe.name}_stress = {probe.expression}",
                  f"meas tran {probe.name} {reduction} {probe.name}_stress"]
    return lines + ([f"print {' '.join(probe.name for probe in probes)}"] if probes else [])


def read_ratings(probes: list[RatingProbe], transcript: str) -> list[RatingCheck]:
    """Judge each measured stress; a missing measurement fails the run rather than passing."""
    measured = {match["name"]: float(match["value"]) for match in PRINTED_RATING.finditer(transcript)}
    missing = [probe.name for probe in probes if probe.name not in measured]
    if missing:
        raise SimulationFailure("Rating measurements were not produced; the run cannot be checked")
    return [RatingCheck(part=probe.part.id, device=probe.device, rating=probe.rating,
                        statistic=probe.statistic, measured=measured[probe.name],
                        limit=probe.limit.value, unit=probe.limit.unit,
                        passed=measured[probe.name] <= probe.limit.value, trust=probe.trust)
            for probe in probes]


def rating_warnings(submitted: SchematicRequest) -> list[str]:
    """State exactly what the ratings check covers and how far to trust it."""
    devices = sorted({part.device for part in submitted.parts if part.device is not None})
    boards = sorted({pin_of(part)[0].id: pin_of(part)[0] for part in submitted.parts
                     if part.kind == "PIN"}.values(), key=lambda board: board.id)
    warnings = ["Parts are checked against their absolute maximums: peak voltage and current on the "
                "solver's own timepoints, and time-averaged power over this run. Resistors use their "
                "package's typical power and working voltage; capacitors their chosen voltage rating, and "
                "electrolytics must never see reverse voltage. Inductor current and saturation, and sources, "
                "are not checked."]
    if devices:
        warnings.append("Device current is measured into terminal 0 (drain, collector or output); "
                        "BJT power omits the small base term. Op-amps and regulators are behavioral "
                        "models and do not current-limit: an iout_max failure means the real part "
                        "would limit or fail.")
    if boards:
        warnings.append("Board pins are modelled at their default drive with ESD clamp diodes to the "
                        "logic rail and ground; firmware behaviour is not simulated. The board's GND "
                        "is the circuit ground.")
    drafts = [device for device in devices if LIBRARY[device].trust.level == "draft"]
    drafts += [board.id for board in boards if board.trust.level == "draft"]
    if drafts:
        warnings.append(f"Draft parts ({', '.join(drafts)}): models and ratings are unconfirmed "
                        "against datasheets, so a pass is not hardware approval.")
    return warnings
