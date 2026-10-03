"""Pure graph validation and deterministic terminal-to-node assignment."""

from backend.schematic_models import Part, Pin, SchematicRequest


def pin_key(pin: Pin) -> str:
    """Identify a terminal without relying on visual coordinates."""
    return f"{pin.part}:{pin.terminal}"


def part_pins(part: Part) -> list[str]:
    """Ground has one terminal; all other supported parts have two."""
    return [f"{part.id}:{terminal}" for terminal in range(1 if part.kind == "GND" else 2)]


def merge_sets(groups: list[set[str]], first: str, second: str) -> list[set[str]]:
    """Return connection groups with the two referenced terminals joined."""
    joined = set().union(*(group for group in groups if first in group or second in group))
    return [group for group in groups if first not in group and second not in group] + [joined]


def validate_wires(submitted: SchematicRequest, pins: set[str]) -> None:
    """Reject missing pins, self-links, duplicate wires and unwired terminals."""
    connected: set[str] = set()
    edges: set[frozenset[str]] = set()
    for wire in submitted.wires:
        first, second = pin_key(wire.a), pin_key(wire.b)
        if first not in pins or second not in pins:
            raise ValueError("A wire references a missing terminal")
        edge = frozenset((first, second))
        if len(edge) != 2 or edge in edges:
            raise ValueError("Remove self-links or duplicate wires")
        edges.add(edge)
        connected.update(edge)
    if connected != pins:
        raise ValueError("Connect every terminal explicitly, including ground")


def validate_ground_path(submitted: SchematicRequest, nodes: dict[str, str]) -> None:
    """Reject floating islands before invoking the solver."""
    reachable = {"0"}
    edges = [set(nodes[pin] for pin in part_pins(part)) for part in submitted.parts]
    for _ in submitted.parts:
        reachable |= set().union(*(edge for edge in edges if edge & reachable))
    if reachable != set(nodes.values()):
        raise ValueError("Every component must have a path to ground; remove floating islands")
    for part in submitted.parts:
        if part.kind != "GND" and nodes[f"{part.id}:0"] == nodes[f"{part.id}:1"]:
            raise ValueError(f"{part.id} has shorted terminals; remove the bypass wire")


def assign_nodes(submitted: SchematicRequest) -> dict[str, str]:
    """Validate topology and assign safe generated node names, with ground as 0."""
    if len({part.id for part in submitted.parts}) != len(submitted.parts):
        raise ValueError("Component identifiers must be unique")
    pins = {pin for part in submitted.parts for pin in part_pins(part)}
    grounds = {f"{part.id}:0" for part in submitted.parts if part.kind == "GND"}
    if not grounds:
        raise ValueError("Add and connect a ground symbol")
    validate_wires(submitted, pins)
    groups = [{pin} for pin in sorted(pins)]
    for wire in submitted.wires:
        groups = merge_sets(groups, pin_key(wire.a), pin_key(wire.b))
    for ground in sorted(grounds):
        groups = merge_sets(groups, min(grounds), ground)
    groups.sort(key=lambda group: min(group))
    nodes = {pin: "0" if group & grounds else f"n{index}"
             for index, group in enumerate(groups) for pin in group}
    validate_ground_path(submitted, nodes)
    return nodes
