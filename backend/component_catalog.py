"""One component catalog shared by browser, validation and MCP discovery."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, RootModel

DEVICE_KINDS = frozenset({"D", "NMOS", "PMOS", "NPN", "PNP", "OPAMP", "REG"})
TERMINAL_COUNTS = {"GND": 1, "NMOS": 3, "PMOS": 3, "NPN": 3, "PNP": 3, "REG": 3, "OPAMP": 5}


class ComponentDefinition(BaseModel):
    """Static numeric primitive definition, not a manufacturer part rating."""

    model_config = ConfigDict(extra="forbid")
    unit: str
    minimum: float
    maximum: float
    standard_values: list[float]


class ComponentCatalog(RootModel[dict[str, ComponentDefinition]]):
    """The shipped allow-list, loaded independently of client-supplied input."""


CATALOG_PATH = Path(__file__).resolve().parent.parent / "circuits" / "components.json"
COMPONENTS = ComponentCatalog.model_validate_json(CATALOG_PATH.read_text()).root


def terminal_count(kind: str) -> int:
    """Ground one, transistors and regulators three, op-amps five, everything else two."""
    return TERMINAL_COUNTS.get(kind, 2)


def component_definitions() -> list[dict[str, object]]:
    """Describe ideal primitives and the library-backed device kinds honestly."""
    return [{"kind": kind, **definition.model_dump(),
             "terminals": list(range(terminal_count(kind))),
             "model": ("library part: set `device` to a library part id of this kind; value must be 0"
                       if kind in DEVICE_KINDS
                       else "generic ideal; not a manufacturer rating or hardware approval")}
            for kind, definition in COMPONENTS.items()]
