"""Load the curated parts library and generate each part's SPICE model line."""

from pathlib import Path

from backend.part_library_models import LibraryPart

PARTS_ROOT = Path(__file__).resolve().parent.parent / "circuits" / "parts"
INDEX_PATH = Path(__file__).resolve().parent.parent / "circuits" / "parts-index.json"
MODEL_TYPES = {"D": "D", "NMOS": "VDMOS", "PMOS": "VDMOS", "NPN": "NPN", "PNP": "PNP"}


def load_part_file(path: Path, root: Path) -> LibraryPart:
    """Validate one file and require its folder to match its category and id."""
    part = LibraryPart.model_validate_json(path.read_text())
    expected = root / part.category / part.id / "part.json"
    if path.resolve() != expected.resolve():
        raise ValueError(f"{path} must live at {expected.relative_to(root)}")
    return part


def load_library(root: Path = PARTS_ROOT) -> dict[str, LibraryPart]:
    """Load every part file, refusing duplicates so one id always means one part."""
    parts: dict[str, LibraryPart] = {}
    for path in sorted(root.glob("*/*/part.json")):
        try:
            part = load_part_file(path, root)
        except ValueError as error:
            raise ValueError(f"Invalid part file {path.relative_to(root)}: {error}") from error
        if part.id in parts:
            raise ValueError(f"Duplicate part id {part.id}")
        parts[part.id] = part
    return parts


LIBRARY = load_library()


def model_name(part: LibraryPart) -> str:
    """A generated, collision-free SPICE model name, never taken from display text."""
    return f"lib_{part.id}"


def model_card(part: LibraryPart) -> str:
    """Generate the `.model` line from validated numeric parameters only."""
    settings = " ".join(f"{name}={value:.12g}" for name, value in sorted(part.model.parameters.items()))
    channel = "pchan " if part.kind == "PMOS" else ""
    return f".model {model_name(part)} {MODEL_TYPES[part.kind]}({channel}{settings})"


def part_summary(part: LibraryPart) -> dict[str, object]:
    """What the browser and AI clients need to choose and place a part honestly."""
    return {"id": part.id, "name": part.name, "kind": part.kind, "category": part.category,
            "description": part.description, "package": part.package,
            "terminals": list(part.terminals), "trust": part.trust.level,
            "datasheet": part.datasheet.url,
            "ratings": {name: {"value": rating.value, "unit": rating.unit}
                        for name, rating in part.ratings.items()}}


def library_summaries() -> list[dict[str, object]]:
    """Every library part, grouped by category then name."""
    return [part_summary(part) for part in sorted(LIBRARY.values(),
                                                  key=lambda part: (part.category, part.name))]
