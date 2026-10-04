"""One component catalog shared by browser, validation and MCP discovery."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, RootModel


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


def component_definitions() -> list[dict[str, object]]:
    """Describe existing ideal primitives without inventing device models."""
    return [{"kind": kind, **definition.model_dump(),
             "terminals": [0] if kind == "GND" else [0, 1],
             "model": "generic ideal; not a manufacturer rating or hardware approval"}
            for kind, definition in COMPONENTS.items()]
