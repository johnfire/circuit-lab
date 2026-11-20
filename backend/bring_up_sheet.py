"""A first-power-on checklist for a built board, written from one transient simulation.

It names nets and pads exactly as the KiCad export does, so a meter probe can go straight to the
pad. Expected values come from the simulation; real parts differ by their tolerances, so the
sheet asks for "about" and explains what a reading far off points to.
"""

from dataclasses import dataclass

from backend.engineering_notation import engineering_value
from backend.kicad_export import Component, components_for, net_names
from backend.localization import LocalizedString, render_message, text
from backend.part_library import LIBRARY
from backend.schematic_models import Part, SchematicRequest, SchematicResponse, Trace
from backend.schematic_topology import assign_nodes
from backend.support_checks import support_findings

STEADY_FRACTION = 0.02
WARM_FRACTION = 0.7
SOURCE_KINDS = frozenset({"V", "PULSE", "SIN"})
POLARISED = {"D": text("polarity.cathode"), "NMOS": text("polarity.tab"), "PMOS": text("polarity.tab"), "NPN": text("polarity.flat"),
             "PNP": text("polarity.flat"), "OPAMP": text("polarity.notch"), "REG": text("polarity.order")}


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
        return text('bring_up_sheet.describe.about', reading=show(level.final))
    return text('bring_up_sheet.describe.varies_to_a_dc_meter', low=show(level.low), high=show(level.high), average=show(level.average))


def probe_pads(components: list[Component]) -> dict[str, str]:
    """For each node, one pad a probe can touch, preferring a component over a connector."""
    pads: dict[str, str] = {}
    for component in sorted(components, key=lambda component: component.ref.startswith(("J", "TP"))):
        for pad, node in component.pads:
            pads.setdefault(node, text('bring_up_sheet.probe_pads.pad', reference=component.ref, pad=pad))
    return pads


def polarity_lines(parts: list[Part]) -> list[str]:
    """Parts that only work one way round, and what to look for on each."""
    lines: list[str] = [text('bring_up_sheet.polarity_lines.as_on_the_silkscreen', part=part.id, device=LIBRARY[part.device].name, polarity=text('bring_up_sheet.polarity_lines.flat_rim_cathode') if LIBRARY[part.device].category == 'led' else POLARISED[part.kind])
             for part in parts if part.device is not None]
    lines += [text('bring_up_sheet.polarity_lines.electrolytic_to_pad_1', part=part.id) for part in parts
              if part.kind == "C" and part.footprint == "radial"]
    return lines or [text('bring_up_sheet.polarity_lines.no_polarised_parts')]


def supply_lines(parts: list[Part], traces: dict[str, Trace], components: list[Component]) -> list[str]:
    """What to set on the bench supply for each off-board source, with a current limit."""
    connectors = {component.value.removesuffix(" input"): component.ref for component in components
                  if component.value.endswith(" input")}
    lines: list[str] = []
    for part in parts:
        if part.kind not in SOURCE_KINDS or f"I:{part.id}" not in traces:
            continue
        draw = reading([abs(value) for value in traces[f"I:{part.id}"].values])
        limit = max(draw.high * 1.5, draw.high + 0.02)
        lines.append(text('bring_up_sheet.supply_lines.on_pin_1_set_current', part=part.id, connector=connectors.get(part.id, text('bring_up_sheet.supply_lines.its_connector')), voltage=volts(part.value), current=amps(limit), expected=describe(draw, 'A')))
    return lines or [text('bring_up_sheet.supply_lines.no_off_board_supply_the')]


def voltage_rows(names: dict[str, str], pads: dict[str, str], traces: dict[str, Trace]) -> list[str]:
    """One table row per net: where to probe and what to expect."""
    rows: list[str] = [text('bring_up_sheet.voltage_rows.net_probe_expect'), text('bring_up_sheet.voltage_rows.')]
    for node, name in sorted(names.items(), key=lambda item: item[1]):
        trace = traces.get(f"V:{node}")
        if node == "0" or trace is None or node not in pads:
            continue
        rows.append(text('bring_up_sheet.voltage_rows.__2', net=name, pad=pads[node], expected=describe(reading(trace.values), 'V')))
    return rows


def warm_lines(report: SchematicResponse) -> list[str]:
    """Parts near their power or current limit: the ones that get warm. Voltage headroom isn't heat."""
    lines: list[str] = [text('bring_up_sheet.warm_lines.at_of_its_limit', part=check.part, quantity=text('common.power' if check.unit == 'W' else 'common.current'), percent=f'{check.measured / check.limit:.0%}', limit=engineering_value(check.limit, check.unit))
             + (text('bring_up_sheet.warm_lines.exceeded_fix_the_design_before') if not check.passed else text('bring_up_sheet.warm_lines.warm_is_fine_too_hot'))
             for check in report.ratings if check.unit in {"W", "A"} and check.limit > 0
             and check.measured / check.limit >= WARM_FRACTION]
    return lines or [text('bring_up_sheet.warm_lines.nothing_runs_above_70_of')]


def bring_up_sheet(circuit: SchematicRequest, report: SchematicResponse, language: str = "en") -> str:
    """Markdown checklist: before power, first power, voltages, warm parts, open issues."""
    nodes = assign_nodes(circuit)
    components, _ = components_for(circuit, nodes)
    traces = {trace.name: trace for trace in report.traces}
    parts = list(circuit.parts)
    findings = support_findings(circuit, nodes)
    sections = [
        text('bring_up_sheet.bring_up_sheet.bring_up_checklist'), "",
        text('bring_up_sheet.bring_up_sheet.from_simulation_over_ms_real', correlation=report.correlation_id, duration=f'{circuit.timing.stop * 1000:g}'), "",
        text('bring_up_sheet.bring_up_sheet.1_before_power'), "",
        text('bring_up_sheet.bring_up_sheet.look_for_solder_bridges_and'),
        text('bring_up_sheet.bring_up_sheet.meter_on_resistance_each_supply'),
        *polarity_lines(parts), "",
        text('bring_up_sheet.bring_up_sheet.2_first_power_current_limited'), "",
        *supply_lines(parts, traces, components), "",
        text('bring_up_sheet.bring_up_sheet.3_voltages_to_measure_black'), "",
        *voltage_rows(net_names(circuit, nodes), probe_pads(components), traces), "",
        text('bring_up_sheet.bring_up_sheet.4_parts_working_hard_check'), "",
        *warm_lines(report), "",
    ]
    if findings:
        sections += [text('bring_up_sheet.bring_up_sheet.5_open_design_issues'), "", *[text('bring_up_sheet.bring_up_sheet.', finding=finding) for finding in findings], ""]
    if any(part.board_pin is not None for part in parts):
        sections += [text('bring_up_sheet.bring_up_sheet.board_pins_are_driven_by'), ""]
    return "\n".join(render_message(line.reference, language) if isinstance(line, LocalizedString)
                     else line for line in sections)
