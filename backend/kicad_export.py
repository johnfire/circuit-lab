"""Export a complete circuit as a KiCad netlist plus a JLCPCB-style bill of materials.

KiCad's PCB editor imports the netlist (File → Import → Netlist), placing every footprint with its
nets; layout, routing and Gerber/drill output then happen in KiCad. Off-board things become
connectors: each source is a 2-pin header, and board pins land on that board's header connector.
"""

import csv
import io
import uuid
from collections import defaultdict
from dataclasses import dataclass, field

from backend.block_library import free_identifier
from backend.board_library import BOARDS
from backend.footprint_catalog import FootprintOption, chosen_footprint
from backend.part_library import LIBRARY
from backend.schematic_models import Part, SchematicRequest
from backend.schematic_topology import assign_nodes

HEADER_1X2 = "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical"
HEADER_1X1 = "Connector_PinHeader_2.54mm:PinHeader_1x01_P2.54mm_Vertical"
PI_SOCKET = "Connector_PinSocket_2.54mm:PinSocket_2x20_P2.54mm_Vertical"
PI_BOARDS = frozenset({"raspberry_pi_4", "raspberry_pi_5"})
SOURCE_KINDS = frozenset({"V", "PULSE", "SIN"})


@dataclass
class Component:
    """One footprint on the board and which pads join which circuit nodes."""

    ref: str
    value: str
    footprint: str
    lcsc: str | None = None
    pads: list[tuple[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class KicadExport:
    """The files to download, and what the user must still do or check."""

    netlist: str
    bom_csv: str
    warnings: list[str]


def engineering_value(value: float, unit: str) -> str:
    """330, 10k, 4.7u: the compact form PCB values are written in."""
    for scale, prefix in ((1e6, "M"), (1e3, "k"), (1, ""), (1e-3, "m"), (1e-6, "u"), (1e-9, "n"), (1e-12, "p")):
        if abs(value) >= scale:
            return f"{value / scale:.3g}{prefix}{unit}"
    return f"{value:.3g}{unit}"


def quote(text: str) -> str:
    """An S-expression string literal."""
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def part_component(part: Part, nodes: dict[str, str], option: FootprintOption) -> Component:
    """An on-board part: its chosen footprint, with each terminal's pads on that terminal's node."""
    if part.device is not None:
        value = LIBRARY[part.device].name
    else:
        value = engineering_value(part.value, {"R": "", "C": "F", "L": "H"}[part.kind])
    pads = [(pad, nodes[f"{part.id}:{terminal}"]) for terminal, terminal_pads in option.pads.items()
            for pad in terminal_pads]
    return Component(part.id, value, option.kicad, option.lcsc, pads)


def board_connectors(parts: list[Part], nodes: dict[str, str], taken: set[str]) -> tuple[list[Component], list[str]]:
    """One header per board: the Pi's 2x20 socket on its real pins, single pads otherwise."""
    by_board: dict[str, list[Part]] = defaultdict(list)
    for part in parts:
        if part.board_pin is not None:
            by_board[part.board_pin.board].append(part)
    components, warnings = [], []
    for board_id, pins in sorted(by_board.items()):
        board = BOARDS[board_id]
        if board_id in PI_BOARDS:
            ref = free_identifier("J1", taken)
            taken.add(ref)
            pads = [(part.board_pin.pin, nodes[f"{part.id}:0"]) for part in pins if part.board_pin]
            pads += [(pin.id, "0") for pin in board.pins if pin.kind == "ground"]
            components.append(Component(ref, f"{board.name} header", PI_SOCKET, None, pads))
            warnings.append(f"{ref} is the {board.name} 40-pin header: the board plugs in here; all its GND pins are circuit ground.")
            continue
        for label, node in [(part.board_pin.pin, nodes[f"{part.id}:0"]) for part in pins if part.board_pin] + [("GND", "0")]:
            ref = free_identifier("TP1", taken)
            taken.add(ref)
            components.append(Component(ref, f"{board.name} {label}", HEADER_1X1, None, [("1", node)]))
        warnings.append(f"{board.name} pins are single wire pads (TP...); wire each to the board, including GND.")
    return components, warnings


def components_for(circuit: SchematicRequest, nodes: dict[str, str]) -> tuple[list[Component], list[str]]:
    """Every footprint the board needs, plus notes about off-board connections."""
    taken = {part.id for part in circuit.parts}
    components: list[Component] = []
    warnings: list[str] = []
    for part in circuit.parts:
        option = chosen_footprint(part.kind, part.device, part.footprint)
        if option is not None:
            components.append(part_component(part, nodes, option))
            if option.note and part.device is not None:
                warnings.append(f"{part.id} ({option.kicad.split(':')[1]}): {option.note}")
        elif part.kind in SOURCE_KINDS:
            ref = free_identifier("J1", taken)
            taken.add(ref)
            components.append(Component(ref, f"{part.id} input", HEADER_1X2, None,
                                        [("1", nodes[f"{part.id}:0"]), ("2", nodes[f"{part.id}:1"])]))
            warnings.append(f"{part.id} is off-board: connect that supply or signal to {ref} (pin 1 = +).")
    boards, board_notes = board_connectors(list(circuit.parts), nodes, taken)
    return components + boards, warnings + board_notes


def net_names(circuit: SchematicRequest, nodes: dict[str, str]) -> dict[str, str]:
    """GND for ground, a board pin's name where one sits on the net, otherwise N1, N2..."""
    names = {"0": "GND"}
    for part in circuit.parts:
        if part.board_pin is not None:
            pin = BOARDS[part.board_pin.board].pin(part.board_pin.pin)
            node = nodes[f"{part.id}:0"]
            if pin is not None and node not in names and pin.name not in names.values():
                names[node] = pin.name
    for node in sorted(set(nodes.values()) - set(names)):
        names[node] = f"N{node.removeprefix('n')}"
    return names


def netlist_text(components: list[Component], names: dict[str, str]) -> str:
    """KiCad's S-expression netlist (version E), with stable per-reference timestamps."""
    lines = ['(export (version "E")', '  (design (source "circuit-lab") (tool "Circuit Lab"))', "  (components"]
    for component in components:
        stamp = uuid.uuid5(uuid.NAMESPACE_URL, "circuit-lab/" + component.ref)
        fields = f" (fields (field (name \"LCSC\") {quote(component.lcsc)}))" if component.lcsc else ""
        lines.append(f"    (comp (ref {quote(component.ref)}) (value {quote(component.value)}) "
                     f"(footprint {quote(component.footprint)}){fields} "
                     f'(sheetpath (names "/") (tstamps "/")) (tstamps {quote(str(stamp))}))')
    lines.append("  )")
    lines.append("  (nets")
    members: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for component in components:
        for pad, node in component.pads:
            members[node].append((component.ref, pad))
    for code, node in enumerate(sorted(members, key=lambda node: names[node]), start=1):
        nodes_text = " ".join(f"(node (ref {quote(ref)}) (pin {quote(pad)}))" for ref, pad in members[node])
        lines.append(f"    (net (code {quote(str(code))}) (name {quote('/' + names[node])}) {nodes_text})")
    lines += ["  )", ")"]
    return "\n".join(lines) + "\n"


def bom_csv(components: list[Component]) -> str:
    """JLCPCB's BOM columns, identical parts grouped onto one line."""
    groups: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for component in components:
        groups[(component.value, component.footprint.split(":")[1], component.lcsc or "")].append(component.ref)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
    for (value, footprint, lcsc), refs in sorted(groups.items(), key=lambda item: item[1][0]):
        writer.writerow([value, ",".join(refs), footprint, lcsc])
    return buffer.getvalue()


def export_kicad(circuit: SchematicRequest) -> KicadExport:
    """Validate the wiring, then build the netlist, BOM and the honest list of what's left to do."""
    nodes = assign_nodes(circuit)
    components, warnings = components_for(circuit, nodes)
    missing = sorted(component.ref for component in components if not component.lcsc)
    drafts = sorted({part.device for part in circuit.parts if part.device and LIBRARY[part.device].trust.level == "draft"})
    if missing:
        warnings.append(f"No LCSC part number yet for: {', '.join(missing)}. Bare boards are fine; JLC assembly needs them.")
    if drafts:
        warnings.append(f"Draft parts ({', '.join(drafts)}): check each pad map against the datasheet's package drawing before ordering.")
    warnings.append("Import the netlist in KiCad's PCB editor, then place, route, run DRC and plot Gerbers and drill files.")
    return KicadExport(netlist_text(components, net_names(circuit, nodes)), bom_csv(components), warnings)
