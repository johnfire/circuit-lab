"""Validated development-board files: header pinouts and pin-level electrical limits."""

import re
from datetime import date
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from backend.model_primitives import Finite, StrictModel
from backend.part_library_models import DATASHEET_PAGE, Citation, PartId, Rating, Trust

PinId = Annotated[str, Field(pattern=r"^[A-Za-z0-9_+-]{1,8}$")]
PinKind = Literal["gpio", "input_only", "power", "ground", "special"]
PinMode = Literal["output_high", "output_low", "pulse", "input", "input_pull_up",
                  "input_pull_down", "supply"]
GPIO_MODES = frozenset({"output_high", "output_low", "pulse", "input", "input_pull_up",
                        "input_pull_down"})
INPUT_MODES = frozenset({"input", "input_pull_up", "input_pull_down"})
PIN_RATINGS = frozenset({"pin_current_max", "pin_voltage_max", "pin_negative_voltage_max"})


class HeaderPin(StrictModel):
    """One physical pin: where it is, what it is, and what it can do."""

    id: PinId
    name: str = Field(min_length=1, max_length=24, pattern=r"^[A-Za-z0-9 _/().+-]+$")
    kind: PinKind
    gpio: int | None = Field(default=None, ge=0, le=99)
    functions: list[str] = Field(default_factory=list, max_length=8)
    voltage: Finite | None = Field(default=None, gt=0, le=24)
    current_max: Rating | None = None
    fixed_pull_up: Finite | None = Field(default=None, gt=0, le=1e7)
    note: str = Field(default="", max_length=160)

    @model_validator(mode="after")
    def validate_kind(self) -> Self:
        """Power pins carry a voltage and current budget; only GPIO-like pins have a number."""
        if (self.kind == "power") != (self.voltage is not None and self.current_max is not None):
            raise ValueError(f"Pin {self.id}: power pins need voltage and current_max, others neither")
        if self.current_max is not None and self.current_max.unit != "A":
            raise ValueError(f"Pin {self.id}: current_max must be in A")
        if self.gpio is not None and self.kind not in {"gpio", "input_only"}:
            raise ValueError(f"Pin {self.id}: only GPIO pins have a GPIO number")
        return self


class PinElectrical(StrictModel):
    """Shared electrical behaviour of the board's GPIO pins at their default drive setting."""

    logic_voltage: Finite = Field(gt=0, le=6)
    output_resistance: Finite = Field(gt=0, le=10_000)
    pull_resistance: Finite = Field(gt=0, le=1e7)
    ratings: dict[str, Rating]

    @model_validator(mode="after")
    def validate_ratings(self) -> Self:
        """Every board states the same three pin limits, in the right units."""
        if set(self.ratings) != PIN_RATINGS:
            raise ValueError(f"Pin ratings must be exactly: {', '.join(sorted(PIN_RATINGS))}")
        units = {"pin_current_max": "A", "pin_voltage_max": "V", "pin_negative_voltage_max": "V"}
        if any(rating.unit != units[name] for name, rating in self.ratings.items()):
            raise ValueError("Pin current is in A; pin voltages are in V")
        return self


class Board(StrictModel):
    """A development board as the circuit sees it: its header and its pin limits."""

    id: PartId
    name: str = Field(min_length=1, max_length=60)
    description: str = Field(min_length=1, max_length=240)
    header: str = Field(min_length=1, max_length=60)
    columns: Literal[1, 2]
    pins: list[HeaderPin] = Field(min_length=2, max_length=80)
    electrical: PinElectrical
    documentation: str | None = Field(default=None, max_length=300, pattern=r"^https://[^\s]+$")
    sources: Citation
    trust: Trust

    @model_validator(mode="after")
    def validate_board(self) -> Self:
        """Unique pins; verified boards cite their documentation everywhere."""
        if len({pin.id for pin in self.pins}) != len(self.pins):
            raise ValueError("Pin ids must be unique")
        gpios = [pin.gpio for pin in self.pins if pin.gpio is not None]
        if len(set(gpios)) != len(gpios):
            raise ValueError("GPIO numbers must be unique")
        if self.trust.level == "verified":
            validate_verified_board(self)
        return self

    def pin(self, pin_id: str) -> HeaderPin | None:
        """The pin with this id, if the board has it."""
        return next((pin for pin in self.pins if pin.id == pin_id), None)


def validate_verified_board(board: Board) -> None:
    """A verified board names its reviewer and date and cites documentation pages."""
    if not board.trust.reviewed_by or not isinstance(board.trust.reviewed_on, date):
        raise ValueError("A verified board must record who reviewed it and when")
    if not board.documentation:
        raise ValueError("A verified board must link its documentation")
    citations = [board.sources, *(rating.source for rating in board.electrical.ratings.values()),
                 *(pin.current_max.source for pin in board.pins if pin.current_max)]
    if not all(re.search(DATASHEET_PAGE, citation) for citation in citations):
        raise ValueError("Every rating of a verified board must cite a datasheet page")


def allowed_modes(pin: HeaderPin) -> frozenset[str]:
    """What a pin can be set to: supply for power pins, inputs only for input-only pins."""
    if pin.kind == "power":
        return frozenset({"supply"})
    if pin.kind == "input_only":
        return frozenset({"input"})
    return GPIO_MODES if pin.kind == "gpio" else frozenset()
