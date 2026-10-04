"""Bounded frequency-domain contracts with one shared complex-signal axis."""

import math
from typing import Literal, Self

from pydantic import Field, model_validator

from backend.schematic_models import Finite, Identifier, SchematicRequest, StrictModel


class Sweep(StrictModel):
    """Log points per decade or total linear points, never more than 1000 frames."""

    source: Identifier
    amplitude: Finite = Field(gt=0, le=100)
    phase: Finite = Field(ge=-360, le=360)
    start: Finite = Field(ge=.001, le=1e6)
    stop: Finite = Field(ge=.001, le=1e6)
    spacing: Literal["log", "linear"]
    points: int = Field(strict=True, ge=2, le=1000)

    def frequencies(self) -> list[float]:
        """Predict the exact ngspice axis for worker identity verification."""
        if self.spacing == "linear":
            return [self.start + index * (self.stop - self.start) / (self.points - 1)
                    for index in range(self.points)]
        count = math.floor(math.log10(self.stop / self.start) * self.points + 1e-8) + 1
        return [self.start * (self.stop / self.start) ** (index / (count - 1))
                for index in range(count)]

    @model_validator(mode="after")
    def validate_budget(self) -> Self:
        """Reject excessive sweeps before allocating vectors or launching jobs."""
        if self.stop <= self.start:
            raise ValueError("Sweep end must exceed start")
        count = (self.points if self.spacing == "linear" else
                 math.floor(math.log10(self.stop / self.start) * self.points + 1e-8) + 1)
        if not 2 <= count <= 1000:
            raise ValueError("Choose a sweep with 2–1000 frequency points")
        return self


class ACRequest(StrictModel):
    """One structured circuit and one explicit small-signal excitation."""

    circuit: SchematicRequest
    sweep: Sweep

    @model_validator(mode="after")
    def validate_excitation(self) -> Self:
        """Only independent voltage sources can excite the AC analysis."""
        if not any(part.id == self.sweep.source and part.kind in {"V", "PULSE", "SIN"}
                   for part in self.circuit.parts):
            raise ValueError("Select a voltage source for AC excitation")
        return self


class ComplexTrace(StrictModel):
    """Finite real/imaginary samples, with physical units kept distinct."""

    name: str
    unit: Literal["V", "A"]
    real: list[Finite] = Field(min_length=2, max_length=1000)
    imaginary: list[Finite] = Field(min_length=2, max_length=1000)


class ACResponse(StrictModel):
    """Small-signal response about declared DC biases; not transient animation."""

    analysis: Literal["ac"] = "ac"
    status: Literal["completed"] = "completed"
    correlation_id: str
    frequencies: list[Finite] = Field(min_length=2, max_length=1000)
    traces: list[ComplexTrace] = Field(min_length=1, max_length=60)
    pin_nodes: dict[str, str]
    excitation: Sweep
    dc_biases: dict[str, Finite]
    netlist: str
    warnings: list[str]

    @model_validator(mode="after")
    def validate_axis(self) -> Self:
        """Refuse mismatched, non-positive, duplicated or unordered signals."""
        if self.frequencies[0] <= 0 or any(second <= first for first, second in
                                          zip(self.frequencies, self.frequencies[1:])):
            raise ValueError("Frequencies must be positive and increasing")
        if any(len(trace.real) != len(self.frequencies) or
               len(trace.imaginary) != len(self.frequencies) for trace in self.traces):
            raise ValueError("Complex signals must share one frequency axis")
        if len({trace.name for trace in self.traces}) != len(self.traces):
            raise ValueError("Signal names must be unique")
        return self


class ACJob(StrictModel):
    """Allow-listed IPC operation, without executable client input."""

    operation: Literal["schematic_ac"]
    request: ACRequest
    correlation_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
