"""Load curated circuit blocks, merge one into a circuit, and check a block's expectations."""

import re
from pathlib import Path

from backend.block_models import CircuitBlock, Expectation
from backend.schematic_models import SchematicResponse

BLOCKS_ROOT = Path(__file__).resolve().parent.parent / "circuits" / "blocks"
BLOCKS_INDEX_PATH = Path(__file__).resolve().parent.parent / "circuits" / "blocks-index.json"
GRID_X, GRID_Y = (2, 38), (2, 22)
MAX_PARTS, MAX_WIRES = 20, 40


def load_blocks(root: Path = BLOCKS_ROOT) -> dict[str, CircuitBlock]:
    """Load every block file, requiring its file name to match its id."""
    blocks: dict[str, CircuitBlock] = {}
    for path in sorted(root.glob("*.json")):
        try:
            block = CircuitBlock.model_validate_json(path.read_text())
        except ValueError as error:
            raise ValueError(f"Invalid block file {path.name}: {error}") from error
        if path.stem != block.id:
            raise ValueError(f"{path.name} must be named {block.id}.json")
        blocks[block.id] = block
    return blocks


BLOCKS = load_blocks()


def block_summaries() -> list[dict[str, object]]:
    """Every block with its circuit, grouped by category then name."""
    return [block.model_dump(mode="json") for block in
            sorted(BLOCKS.values(), key=lambda block: (block.category, block.name))]


def free_identifier(identifier: str, taken: set[str]) -> str:
    """Keep the id if it's free; otherwise its letter prefix plus the first free number."""
    if identifier not in taken:
        return identifier
    prefix = re.sub(r"\d+$", "", identifier)[:12] or "X"
    number = 1
    while f"{prefix}{number}" in taken:
        number += 1
    return f"{prefix}{number}"


def merge_block(parts: list[dict[str, object]], wires: list[dict[str, object]], block: CircuitBlock,
                column: int, row: int) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Add a block's parts and wires with its top-left part at (column, row), renaming clashes."""
    added = block.circuit.model_dump()
    if len(parts) + len(added["parts"]) > MAX_PARTS or len(wires) + len(added["wires"]) > MAX_WIRES:
        raise ValueError(f"Inserting {block.name} would exceed {MAX_PARTS} parts or {MAX_WIRES} wires")
    left = min(part["x"] for part in added["parts"])
    top = min(part["y"] for part in added["parts"])
    taken = {str(part["id"]) for part in parts}
    renamed: dict[str, str] = {}
    placed = []
    for part in added["parts"]:
        new_id = free_identifier(part["id"], taken)
        taken.add(new_id)
        renamed[part["id"]] = new_id
        x, y = part["x"] - left + column, part["y"] - top + row
        if not (GRID_X[0] <= x <= GRID_X[1] and GRID_Y[0] <= y <= GRID_Y[1]):
            raise ValueError(f"{block.name} doesn't fit at column {column}, row {row}; choose a spot "
                             "further up and to the left")
        placed.append(part | {"id": new_id, "x": x, "y": y})
    linked: list[dict[str, object]] = [{"a": {**wire["a"], "part": renamed[wire["a"]["part"]]},
               "b": {**wire["b"], "part": renamed[wire["b"]["part"]]}} for wire in added["wires"]]
    return parts + placed, wires + linked


def statistic(values: list[float], name: str) -> float:
    """Reduce a trace the way an expectation asks."""
    if name == "final":
        return values[-1]
    if name == "max":
        return max(values)
    if name == "min":
        return min(values)
    settled = values[len(values) // 2:]
    return sum(settled) / len(settled)


def check_expectation(expectation: Expectation, report: SchematicResponse) -> tuple[float, bool]:
    """The measured value and whether it is within tolerance of the stated value."""
    if expectation.signal.startswith("I:"):
        name = expectation.signal
    else:
        node = report.pin_nodes[expectation.signal[2:]]
        name = f"V:{node}"
    trace = next((trace for trace in report.traces if trace.name == name), None)
    values = trace.values if trace else [0.0] * len(report.times)
    measured = statistic(values, expectation.statistic)
    return measured, abs(measured - expectation.value) <= expectation.tolerance
