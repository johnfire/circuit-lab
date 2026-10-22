"""Physical package options for every placeable part, as KiCad footprints with pad maps."""

from dataclasses import dataclass
from pathlib import Path

from pydantic import RootModel

from backend.model_primitives import StrictModel
from backend.part_library import LIBRARY
from backend.part_library_models import TERMINAL_NAMES, KicadFootprint

ROOT = Path(__file__).resolve().parent.parent / "circuits"
GENERIC_PATH = ROOT / "footprints.json"
VERIFIED_PATH = ROOT / "kicad-footprints-verified.txt"


class GenericFootprint(StrictModel):
    """A package option for an ideal two-terminal part; terminal 0 is pad 1, terminal 1 is pad 2."""

    id: str
    mount: str
    kicad: KicadFootprint
    note: str


class GenericCatalog(RootModel[dict[str, list[GenericFootprint]]]):
    """Options per ideal kind (R, C, L)."""


GENERIC = GenericCatalog.model_validate_json(GENERIC_PATH.read_text()).root


@dataclass(frozen=True)
class FootprintOption:
    """One choice, normalized: pads per terminal index, ready for the netlist."""

    id: str
    mount: str
    kicad: str
    pads: dict[int, tuple[str, ...]]
    lcsc: str | None
    note: str


def footprint_options(kind: str, device: str | None) -> list[FootprintOption]:
    """The package choices for a part; empty for ground, sources and board pins (off-board)."""
    if kind in GENERIC:
        return [FootprintOption(option.id, option.mount, option.kicad, {0: ("1",), 1: ("2",)}, None, option.note)
                for option in GENERIC[kind]]
    if device is None or device not in LIBRARY:
        return []
    names = TERMINAL_NAMES[kind]
    return [FootprintOption(option.id, option.mount, option.kicad,
                            {names.index(name): tuple(pads) for name, pads in option.pads.items()},
                            option.lcsc, option.note) for option in LIBRARY[device].footprints]


def chosen_footprint(kind: str, device: str | None, choice: str | None) -> FootprintOption | None:
    """The selected option, or the first one when the part hasn't chosen."""
    options = footprint_options(kind, device)
    if not options:
        return None
    return next((option for option in options if option.id == choice), options[0])


def verified_footprints() -> set[str]:
    """KiCad footprint names confirmed to exist in KiCad's official library."""
    return {line.strip() for line in VERIFIED_PATH.read_text().splitlines()
            if line.strip() and not line.startswith("#")}
