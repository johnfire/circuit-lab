"""Curated circuit blocks: complete, simulatable circuits that state what they should do."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from backend.component_catalog import terminal_count
from backend.model_primitives import Finite, StrictModel
from backend.part_library_models import PartId
from backend.schematic_models import SchematicRequest

Text = Annotated[str, Field(min_length=1, max_length=300, pattern=r"^[^\x00-\x1f\x7f]+$")]
SignalName = Annotated[str, Field(pattern=r"^(V:[a-zA-Z][a-zA-Z0-9_]{0,15}:[0-4]|I:[a-zA-Z][a-zA-Z0-9_]{0,15})$")]


class Expectation(StrictModel):
    """One functional claim about the block, checked against a real simulation in CI."""

    signal: SignalName
    statistic: Literal["final", "max", "min", "settled_mean"]
    value: Finite
    tolerance: Finite = Field(gt=0)
    meaning: Text


class CircuitBlock(StrictModel):
    """A reusable building block, insertable into any circuit or openable on its own."""

    id: PartId
    name: Text
    category: Literal["indicators", "switching", "interfacing", "signal", "power"]
    description: Text
    notes: Text
    expectations: list[Expectation] = Field(min_length=1, max_length=8)
    circuit: SchematicRequest

    @model_validator(mode="after")
    def validate_expectations(self) -> Self:
        """Every expectation names a part, and a terminal, that the block really has."""
        terminals = {part.id: terminal_count(part.kind) for part in self.circuit.parts}
        for expectation in self.expectations:
            parts = expectation.signal.split(":")
            if parts[1] not in terminals or (len(parts) == 3 and int(parts[2]) >= terminals[parts[1]]):
                raise ValueError(f"{self.id}: expectation {expectation.signal} names a missing terminal")
        return self
