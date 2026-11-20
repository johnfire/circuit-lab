"""Datasheet support parts: the capacitors a regulator or op-amp needs, found on the wiring.

A behavioral model cannot oscillate or pick up supply noise, so a missing output capacitor or
bypass capacitor passes simulation and fails on the bench. These rules come from each part's
datasheet and are checked on the connections alone, before and independently of any simulation.
"""

from dataclasses import dataclass

from backend.engineering_notation import engineering_value
from backend.footprint_catalog import chosen_footprint
from backend.localization import catalogue_value, text
from backend.part_library import LIBRARY
from backend.part_library_models import TERMINAL_NAMES, SupportRule
from backend.schematic_models import Part, SchematicRequest

TERMINAL_LABELS = {"output": "OUT", "input": "IN", "ground_or_adjust": "GND/ADJ", "v_plus": "V+",
                   "v_minus": "V-", "GND": text("support.ground")}


@dataclass(frozen=True)
class Capacitor:
    """One placed capacitor: the two nodes it joins, its value and whether it is ceramic."""

    id: str
    nodes: frozenset[str]
    farads: float
    is_ceramic: bool


def placed_capacitors(parts: list[Part], nodes: dict[str, str]) -> list[Capacitor]:
    """Every capacitor in the circuit, with its dielectric taken from its chosen package."""
    capacitors = []
    for part in parts:
        if part.kind != "C":
            continue
        option = chosen_footprint("C", None, part.footprint)
        capacitors.append(Capacitor(part.id, frozenset({nodes[f"{part.id}:0"], nodes[f"{part.id}:1"]}),
                                    part.value, option is None or option.dielectric == "ceramic"))
    return capacitors


def rule_node(part: Part, terminal: str, nodes: dict[str, str]) -> str:
    """The circuit node behind a terminal name, or ground for "GND"."""
    if terminal == "GND":
        return "0"
    return nodes[f"{part.id}:{TERMINAL_NAMES[part.kind].index(terminal)}"]


def rule_finding(part: Part, rule: SupportRule, nodes: dict[str, str], capacitors: list[Capacitor]) -> str | None:
    """A sentence saying what is missing, or None when the wiring satisfies the rule."""
    pair = frozenset(rule_node(part, terminal, nodes) for terminal in rule.between)
    if len(pair) == 1:
        return None
    present = [capacitor for capacitor in capacitors if capacitor.nodes == pair]
    counted = sum(capacitor.farads for capacitor in present if rule.ceramic or not capacitor.is_ceramic)
    if counted >= rule.capacitance_min * 0.999:
        return None
    first, second = (TERMINAL_LABELS.get(terminal, terminal) for terminal in rule.between)
    purpose_index = LIBRARY[str(part.device)].support.index(rule)
    purpose = catalogue_value(f"catalogue.support.{part.device}.{purpose_index}.purpose", rule.purpose)
    need = (text('support_checks.rule_finding.needs_between_and', level=text("support." + rule.level), part=part.id, device=LIBRARY[str(part.device)].name, capacitance=engineering_value(rule.capacitance_min, 'F'), first=first, second=second, purpose=purpose, source=rule.source))
    ceramics = [capacitor.id for capacitor in present if capacitor.is_ceramic and not rule.ceramic]
    if ceramics:
        return need + text('support_checks.rule_finding.is_ceramic_which_this_part', capacitors=', '.join(ceramics))
    found = engineering_value(counted, "F") if present else text("common.none")
    return need + text('support_checks.rule_finding.found', found=found)


def support_findings(circuit: SchematicRequest, nodes: dict[str, str]) -> list[str]:
    """Every unmet datasheet support rule, required ones first."""
    capacitors = placed_capacitors(list(circuit.parts), nodes)
    findings = [(rule.level, rule_finding(part, rule, nodes, capacitors))
                for part in circuit.parts if part.device is not None
                for rule in LIBRARY[part.device].support]
    return [text for level in ("required", "recommended") for rule_level, text in findings
            if rule_level == level and text is not None]
