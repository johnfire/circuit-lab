"""A first-power-on checklist for a built board, written from one transient simulation.

It names nets and pads exactly as the KiCad export does, so a meter probe can go straight to the
pad. Expected values come from the simulation; real parts differ by their tolerances, so the
sheet asks for "about" and explains what a reading far off points to.
"""

from dataclasses import dataclass

from backend.engineering_notation import engineering_value
from backend.kicad_export import Component, components_for, net_names
from backend.part_library import LIBRARY
from backend.schematic_models import Part, SchematicRequest, SchematicResponse, Trace
from backend.schematic_topology import assign_nodes
from backend.support_checks import support_findings

STEADY_FRACTION = 0.02
WARM_FRACTION = 0.7
SOURCE_KINDS = frozenset({"V", "PULSE", "SIN"})
POLARISED = {"D": "cathode band", "NMOS": "tab/flat side", "PMOS": "tab/flat side", "NPN": "flat side",
             "PNP": "flat side", "OPAMP": "pin 1 notch", "REG": "tab and pin order"}


@dataclass(frozen=True)
class Reading:
    """What a meter should show on one net over the simulated run."""

    final: float
    low: float
    high: float
    average: float

    @property
    def is_steady(self) -> bool:
        """True when the net settles: a DC meter reading means something."""
        return self.high - self.low <= STEADY_FRACTION * max(abs(self.high), abs(self.low), 0.1)


def reading(values: list[float]) -> Reading:
    """Summary statistics of one sampled trace."""
    return Reading(values[-1], min(values), max(values), sum(values) / len(values))


def volts(value: float) -> str:
    return engineering_value(value, "V") if abs(value) >= 1e-3 else "0V"


def amps(value: float) -> str:
    return engineering_value(abs(value), "A") if abs(value) >= 1e-6 else "0A"


def describe(level: Reading, unit: str) -> str:
    """'about 3.3V', or the range and average a meter would show for a changing signal."""
    show = volts if unit == "V" else amps
    if level.is_steady:
        return f"about {show(level.final)}"
    return f"varies {show(level.low)} to {show(level.high)}; a DC meter shows about {show(level.average)}"


def probe_pads(components: list[Component]) -> dict[str, str]:
    """For each node, one pad a probe can touch, preferring a component over a connector."""
    pads: dict[str, str] = {}
    for component in sorted(components, key=lambda component: component.ref.startswith(("J", "TP"))):
        for pad, node in component.pads:
            pads.setdefault(node, f"{component.ref} pad {pad}")
    return pads


def polarity_lines(parts: list[Part]) -> list[str]:
    """Parts that only work one way round, and what to look for on each."""
    lines = [f"- [ ] {part.id} ({LIBRARY[part.device].name}): "
             f"{'flat rim (cathode)' if LIBRARY[part.device].category == 'led' else POLARISED[part.kind]} as on the silkscreen"
             for part in parts if part.device is not None]
    lines += [f"- [ ] {part.id}: electrolytic, + to pad 1" for part in parts
              if part.kind == "C" and part.footprint == "radial"]
    return lines or ["- [ ] No polarised parts."]


def supply_lines(parts: list[Part], traces: dict[str, Trace], components: list[Component]) -> list[str]:
    """What to set on the bench supply for each off-board source, with a current limit."""
    connectors = {component.value.removesuffix(" input"): component.ref for component in components
                  if component.value.endswith(" input")}
    lines = []
    for part in parts:
        if part.kind not in SOURCE_KINDS or f"I:{part.id}" not in traces:
            continue
        draw = reading([abs(value) for value in traces[f"I:{part.id}"].values])
        limit = max(draw.high * 1.5, draw.high + 0.02)
        lines.append(f"- [ ] {part.id} on {connectors.get(part.id, 'its connector')} pin 1 (+): set "
                     f"{volts(part.value)}, current limit {amps(limit)}. Expected draw: {describe(draw, 'A')}. "
                     "Far more means a short or a reversed part: switch off at once.")
    return lines or ["- [ ] No off-board supply: the board is powered through its header."]


def voltage_rows(names: dict[str, str], pads: dict[str, str], traces: dict[str, Trace]) -> list[str]:
    """One table row per net: where to probe and what to expect."""
    rows = ["| Net | Probe | Expect |", "| --- | --- | --- |"]
    for node, name in sorted(names.items(), key=lambda item: item[1]):
        trace = traces.get(f"V:{node}")
        if node == "0" or trace is None or node not in pads:
            continue
        rows.append(f"| /{name} | {pads[node]} | {describe(reading(trace.values), 'V')} |")
    return rows


def warm_lines(report: SchematicResponse) -> list[str]:
    """Parts near their power or current limit: the ones that get warm. Voltage headroom isn't heat."""
    lines = [f"- [ ] {check.part}: {'power' if check.unit == 'W' else 'current'} at "
             f"{check.measured / check.limit:.0%} of its {engineering_value(check.limit, check.unit)} limit"
             + (" (EXCEEDED: fix the design before building)" if not check.passed else ": warm is fine, too hot to touch is not")
             for check in report.ratings if check.unit in {"W", "A"} and check.limit > 0
             and check.measured / check.limit >= WARM_FRACTION]
    return lines or ["- Nothing runs above 70% of its power or current limit."]


def bring_up_sheet(circuit: SchematicRequest, report: SchematicResponse) -> str:
    """Markdown checklist: before power, first power, voltages, warm parts, open issues."""
    nodes = assign_nodes(circuit)
    components, _ = components_for(circuit, nodes)
    traces = {trace.name: trace for trace in report.traces}
    parts = list(circuit.parts)
    findings = support_findings(circuit, nodes)
    sections = [
        "# Bring-up checklist", "",
        f"From simulation {report.correlation_id} over {circuit.timing.stop * 1000:g} ms. Real parts differ "
        "by their tolerances (often 5–10%); a reading far from \"about\" points at a part on that net.", "",
        "## 1. Before power", "",
        "- [ ] Look for solder bridges and unsoldered pads, especially on headers.",
        "- [ ] Meter on resistance: each supply's + to GND must not read near 0 Ω.",
        *polarity_lines(parts), "",
        "## 2. First power, current-limited", "",
        *supply_lines(parts, traces, components), "",
        "## 3. Voltages to measure (black probe on GND)", "",
        *voltage_rows(net_names(circuit, nodes), probe_pads(components), traces), "",
        "## 4. Parts working hard (check they only get warm)", "",
        *warm_lines(report), "",
    ]
    if findings:
        sections += ["## 5. Open design issues", "", *[f"- {finding}" for finding in findings], ""]
    if any(part.board_pin is not None for part in parts):
        sections += ["Board pins are driven by firmware: set each pin to the mode used in the simulation "
                     "before comparing readings.", ""]
    return "\n".join(sections)
