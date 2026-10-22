"""Measure every library device's stress on the solver's own timepoints and judge its ratings.

Peaks are taken by ngspice `meas` on the raw transient solution, before resampling to output
frames, so a spike shorter than the frame interval is still caught.
"""

import re
from dataclasses import dataclass
from typing import Literal

from backend.part_library import LIBRARY
from backend.part_library_models import LibraryPart
from backend.schematic_models import Part, RatingCheck, SchematicRequest
from backend.simulation_engine import SimulationFailure

PRINTED_RATING = re.compile(r"^(?P<name>rating\d+)\s*=\s*(?P<value>[-+0-9.eE]+)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class RatingProbe:
    """One generated measurement: which rating, how it is reduced, and its SPICE expression."""

    name: str
    part: Part
    library_part: LibraryPart
    rating: str
    statistic: Literal["peak", "average"]
    expression: str


def positive(expression: str) -> str:
    """Elementwise max(x, 0), written with operators ngspice vectors support."""
    return f"(({expression})+abs({expression}))/2"


def stress_expressions(kind: str, voltages: list[str], current: str) -> dict[str, str]:
    """SPICE vector expressions for each rating a device family can have."""
    v0, v1 = voltages[0], voltages[1]
    if kind == "D":
        return {"if_max": positive(current), "vr_max": positive(f"{v1}-{v0}"),
                "iz_max": positive(f"-{current}"), "pd_max": f"abs(({v0}-{v1})*{current})"}
    v2 = voltages[2]
    main = {"pd_max": f"abs(({v0}-{v2})*{current})"}
    if kind in {"NMOS", "PMOS"}:
        return main | {"vds_max": f"abs({v0}-{v2})", "vgs_max": f"abs({v1}-{v2})",
                       "id_max": f"abs({current})"}
    return main | {"vceo_max": f"abs({v0}-{v2})", "ic_max": f"abs({current})"}


def rating_probes(submitted: SchematicRequest, nodes: dict[str, str]) -> list[RatingProbe]:
    """Every rating of every library device, in a stable order."""
    probes: list[RatingProbe] = []
    for index, part in enumerate(submitted.parts):
        if part.device is None:
            continue
        library_part = LIBRARY[part.device]
        voltages = ["0" if nodes[pin] == "0" else f"v({nodes[pin]})"
                    for pin in (f"{part.id}:{terminal}" for terminal in range(len(library_part.terminals)))]
        expressions = stress_expressions(part.kind, voltages, f"i(Vprobe{index})")
        for rating in sorted(library_part.ratings):
            probes.append(RatingProbe(name=f"rating{len(probes)}", part=part,
                                      library_part=library_part, rating=rating,
                                      statistic="average" if rating == "pd_max" else "peak",
                                      expression=expressions[rating]))
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
    return [RatingCheck(part=probe.part.id, device=probe.library_part.id, rating=probe.rating,
                        statistic=probe.statistic, measured=measured[probe.name],
                        limit=probe.library_part.ratings[probe.rating].value,
                        unit=probe.library_part.ratings[probe.rating].unit,
                        passed=measured[probe.name] <= probe.library_part.ratings[probe.rating].value,
                        trust=probe.library_part.trust.level)
            for probe in probes]


def rating_warnings(submitted: SchematicRequest) -> list[str]:
    """State exactly what the ratings check covers and how far to trust it."""
    devices = sorted({part.device for part in submitted.parts if part.device is not None})
    if not devices:
        return ["Ideal R/C/L and sources only; no component ratings or Pi GPIO protection checks."]
    drafts = [device for device in devices if LIBRARY[device].trust.level == "draft"]
    warnings = ["Library devices are checked against their absolute-maximum ratings: peak voltage "
                "and current on the solver's own timepoints, and time-averaged power over this run. "
                "R/C/L and sources stay ideal.",
                "Transistor current is measured into terminal 0 (drain/collector); BJT power "
                "omits the small base-emitter term. No Pi GPIO protection checks."]
    if drafts:
        warnings.append(f"Draft parts ({', '.join(drafts)}): models and ratings are unconfirmed "
                        "against datasheets, so a pass is not hardware approval.")
    return warnings
