"""Netlist lines for library devices and their model cards, shared by every analysis."""

from collections.abc import Sequence

from backend.component_catalog import terminal_count
from backend.part_library import LIBRARY, SPICE_PREFIX, model_card, model_name
from backend.schematic_models import Part


def device_lines(part: Part, index: int, nodes: dict[str, str]) -> list[str]:
    """Probe the current into terminal 0, then place the device on generated nodes."""
    if part.device is None:
        raise ValueError(f"{part.id} is not a library device")
    terminals = [nodes[f"{part.id}:{terminal}"] for terminal in range(terminal_count(part.kind))]
    internal = f"p{index}"
    connections = " ".join([internal, *terminals[1:]])
    return [f"Vprobe{index} {terminals[0]} {internal} 0",
            f"{SPICE_PREFIX[part.kind]}{index} {connections} {model_name(LIBRARY[part.device])}"]


def model_cards(parts: Sequence[Part]) -> list[str]:
    """One generated `.model` line per distinct library part used."""
    return [model_card(LIBRARY[device])
            for device in sorted({part.device for part in parts if part.device is not None})]
