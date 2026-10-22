"""Validated library part files: identity, model parameters, ratings, tests and trust."""

import re
from datetime import date
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from backend.model_primitives import Finite, StrictModel

PartId = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_]{0,31}$")]
ParameterName = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9]{0,11}$")]
Citation = Annotated[str, Field(min_length=3, max_length=240, pattern=r"^[^\x00-\x1f\x7f]+$")]
DeviceKind = Literal["D", "NMOS", "PMOS", "NPN", "PNP", "OPAMP", "REG"]
Category = Literal["diode", "schottky", "zener", "led", "mosfet", "bjt", "opamp", "regulator"]

DATASHEET_PAGE = r"(?i)datasheet p\.\s*\d+"
CATEGORY_KINDS: dict[str, frozenset[str]] = {
    "diode": frozenset({"D"}), "schottky": frozenset({"D"}), "zener": frozenset({"D"}),
    "led": frozenset({"D"}), "mosfet": frozenset({"NMOS", "PMOS"}), "bjt": frozenset({"NPN", "PNP"}),
    "opamp": frozenset({"OPAMP"}), "regulator": frozenset({"REG"}),
}
REQUIRED_RATINGS: dict[str, frozenset[str]] = {
    "diode": frozenset({"vr_max", "if_max"}), "schottky": frozenset({"vr_max", "if_max"}),
    "led": frozenset({"vr_max", "if_max"}), "zener": frozenset({"iz_max", "pd_max"}),
    "mosfet": frozenset({"vds_max", "vgs_max", "id_max", "pd_max"}),
    "bjt": frozenset({"vceo_max", "ic_max", "pd_max"}),
    "opamp": frozenset({"vs_max", "iout_max"}),
    "regulator": frozenset({"vin_max", "iout_max", "pd_max"}),
}
OPTIONAL_RATINGS: dict[str, frozenset[str]] = {
    "diode": frozenset({"pd_max"}), "schottky": frozenset({"pd_max"}), "led": frozenset({"pd_max"}),
    "zener": frozenset({"if_max"}), "mosfet": frozenset(), "bjt": frozenset(),
    "opamp": frozenset(), "regulator": frozenset(),
}
RATING_UNITS = {"vr_max": "V", "if_max": "A", "iz_max": "A", "pd_max": "W", "vds_max": "V",
                "vgs_max": "V", "id_max": "A", "vceo_max": "V", "ic_max": "A",
                "vs_max": "V", "iout_max": "A", "vin_max": "V"}
TERMINAL_NAMES: dict[str, tuple[str, ...]] = {
    "D": ("anode", "cathode"), "NMOS": ("drain", "gate", "source"),
    "PMOS": ("drain", "gate", "source"), "NPN": ("collector", "base", "emitter"),
    "PNP": ("collector", "base", "emitter"),
    "OPAMP": ("output", "in_plus", "in_minus", "v_plus", "v_minus"),
    "REG": ("output", "input", "ground_or_adjust"),
}
TEMPLATE_PARAMETERS: dict[str, frozenset[str]] = {
    "OPAMP": frozenset({"AOL", "GBW", "SR", "VOS", "ISUP", "VOHDROP", "VOLDROP", "RIN", "ROUT"}),
    "REG": frozenset({"VREG", "DROPOUT", "IQ"}),
}


class Rating(StrictModel):
    """One absolute maximum, as a positive magnitude, with where the number came from."""

    value: Finite = Field(gt=0, le=10_000)
    unit: Literal["V", "A", "W"]
    source: Citation


class SpecBounds(StrictModel):
    """A measured quantity must fall inside at least one stated bound."""

    min: Finite | None = None
    max: Finite | None = None
    source: Citation

    @model_validator(mode="after")
    def validate_bounds(self) -> Self:
        """Require a bound, and an ordered pair when both are given."""
        if self.min is None and self.max is None:
            raise ValueError("A characterization test needs a min or a max")
        if self.min is not None and self.max is not None and self.min >= self.max:
            raise ValueError("Characterization min must be below max")
        return self


class DiodeForwardVoltage(SpecBounds):
    """Forward voltage at a forced forward current."""

    test: Literal["diode_forward_voltage"]
    current: Finite = Field(gt=0, le=10)


class ZenerVoltage(SpecBounds):
    """Reverse breakdown voltage at a forced reverse current."""

    test: Literal["zener_voltage"]
    current: Finite = Field(gt=0, le=1)


class MosfetThreshold(SpecBounds):
    """Gate-source voltage magnitude at a drain current, with gate tied to drain."""

    test: Literal["mosfet_threshold"]
    drain_current: Finite = Field(gt=0, le=0.1)


class MosfetOnResistance(SpecBounds):
    """Drain-source resistance at a gate drive magnitude and drain current."""

    test: Literal["mosfet_on_resistance"]
    gate_voltage: Finite = Field(gt=0, le=20)
    drain_current: Finite = Field(gt=0, le=100)


class BjtCurrentGain(SpecBounds):
    """DC current gain hFE at a collector-emitter voltage and collector current."""

    test: Literal["bjt_current_gain"]
    collector_voltage: Finite = Field(gt=0, le=50)
    collector_current: Finite = Field(gt=0, le=5)


class BjtSaturationVoltage(SpecBounds):
    """Collector-emitter saturation voltage at forced collector and base currents."""

    test: Literal["bjt_saturation_voltage"]
    collector_current: Finite = Field(gt=0, le=5)
    base_current: Finite = Field(gt=0, le=1)


class OpampUnityGainBandwidth(SpecBounds):
    """−3 dB frequency of a unity-gain follower biased at mid-supply, in Hz."""

    test: Literal["opamp_unity_gain_bandwidth"]
    supply: Finite = Field(gt=0, le=40)


class OpampSlewRate(SpecBounds):
    """Peak output rate of change of a follower stepped across half the supply, in V/s."""

    test: Literal["opamp_slew_rate"]
    supply: Finite = Field(gt=0, le=40)


class OpampOutputHigh(SpecBounds):
    """Output voltage when driven high into a load to ground, on a single supply."""

    test: Literal["opamp_output_high"]
    supply: Finite = Field(gt=0, le=40)
    load_resistance: Finite = Field(gt=0, le=1e9)


class RegulatorOutputVoltage(SpecBounds):
    """Output at an input voltage and load current; adjustable parts use a divider."""

    test: Literal["regulator_output_voltage"]
    input_voltage: Finite = Field(gt=0, le=60)
    load_current: Finite = Field(ge=0, le=5)
    adjust_top: Finite | None = Field(default=None, gt=0, le=1e7)
    adjust_bottom: Finite | None = Field(default=None, gt=0, le=1e7)

    @model_validator(mode="after")
    def validate_divider(self) -> Self:
        """An adjust divider needs both resistors or neither."""
        if (self.adjust_top is None) != (self.adjust_bottom is None):
            raise ValueError("Give both adjust_top and adjust_bottom, or neither")
        return self


Characterization = Annotated[
    DiodeForwardVoltage | ZenerVoltage | MosfetThreshold | MosfetOnResistance
    | BjtCurrentGain | BjtSaturationVoltage | OpampUnityGainBandwidth | OpampSlewRate
    | OpampOutputHigh | RegulatorOutputVoltage, Field(discriminator="test")]

TEST_KINDS: dict[str, frozenset[str]] = {
    "diode_forward_voltage": frozenset({"D"}), "zener_voltage": frozenset({"D"}),
    "mosfet_threshold": frozenset({"NMOS", "PMOS"}),
    "mosfet_on_resistance": frozenset({"NMOS", "PMOS"}),
    "bjt_current_gain": frozenset({"NPN", "PNP"}),
    "bjt_saturation_voltage": frozenset({"NPN", "PNP"}),
    "opamp_unity_gain_bandwidth": frozenset({"OPAMP"}), "opamp_slew_rate": frozenset({"OPAMP"}),
    "opamp_output_high": frozenset({"OPAMP"}), "regulator_output_voltage": frozenset({"REG"}),
}


class Datasheet(StrictModel):
    """Where a reviewer checks the numbers; required before verification."""

    manufacturer: str | None = Field(default=None, max_length=80)
    url: str | None = Field(default=None, max_length=300, pattern=r"^https://[^\s]+$")


class Trust(StrictModel):
    """Only a named human review against the datasheet makes a part verified."""

    level: Literal["draft", "verified"]
    reviewed_by: str | None = Field(default=None, max_length=80)
    reviewed_on: date | None = None
    notes: str = Field(default="", max_length=600)


class DeviceModel(StrictModel):
    """Named numeric SPICE parameters; the model line itself is generated by our code."""

    parameters: dict[ParameterName, Finite] = Field(min_length=1, max_length=40)


class LibraryPart(StrictModel):
    """One curated real component, usable in circuits and checked against its ratings."""

    id: PartId
    name: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9 ._()/+-]+$")
    kind: DeviceKind
    category: Category
    description: str = Field(min_length=1, max_length=240)
    package: str = Field(min_length=1, max_length=40)
    datasheet: Datasheet
    model: DeviceModel
    ratings: dict[str, Rating]
    characterization: list[Characterization] = Field(min_length=1, max_length=8)
    trust: Trust

    @model_validator(mode="after")
    def validate_consistency(self) -> Self:
        """Match kind, ratings and tests to the category before trusting the file."""
        if self.kind not in CATEGORY_KINDS[self.category]:
            raise ValueError(f"A {self.category} cannot be kind {self.kind}")
        validate_rating_names(self)
        validate_template_parameters(self)
        for test in self.characterization:
            if self.kind not in TEST_KINDS[test.test]:
                raise ValueError(f"{test.test} does not apply to kind {self.kind}")
        if self.trust.level == "verified":
            validate_verified(self)
        return self

    @property
    def terminals(self) -> tuple[str, ...]:
        """Terminal names, in the order the schematic numbers them."""
        return TERMINAL_NAMES[self.kind]


def validate_rating_names(part: LibraryPart) -> None:
    """Require the category's ratings, allow its optional ones, and check their units."""
    names = set(part.ratings)
    missing = REQUIRED_RATINGS[part.category] - names
    unknown = names - REQUIRED_RATINGS[part.category] - OPTIONAL_RATINGS[part.category]
    if missing:
        raise ValueError(f"Missing ratings: {', '.join(sorted(missing))}")
    if unknown:
        raise ValueError(f"Unknown ratings for {part.category}: {', '.join(sorted(unknown))}")
    for name, rating in part.ratings.items():
        if rating.unit != RATING_UNITS[name]:
            raise ValueError(f"{name} must be in {RATING_UNITS[name]}")


def validate_template_parameters(part: LibraryPart) -> None:
    """Subcircuit templates need exactly their named parameters, with sane values."""
    required = TEMPLATE_PARAMETERS.get(part.kind)
    if required is None:
        return
    names = set(part.model.parameters)
    if names != required:
        raise ValueError(f"{part.kind} parameters must be exactly: {', '.join(sorted(required))}")
    values = part.model.parameters
    positive = {"OPAMP": ("AOL", "GBW", "SR", "RIN", "ROUT"), "REG": ("VREG", "DROPOUT")}[part.kind]
    if any(values[name] <= 0 for name in positive):
        raise ValueError(f"{', '.join(positive)} must be positive")


def validate_verified(part: LibraryPart) -> None:
    """A verified part names its reviewer and date, and cites datasheet pages throughout."""
    if not part.trust.reviewed_by or not part.trust.reviewed_on:
        raise ValueError("A verified part must record who reviewed it and when")
    if not part.datasheet.url:
        raise ValueError("A verified part must link its datasheet")
    citations = ([rating.source for rating in part.ratings.values()]
                 + [test.source for test in part.characterization])
    if not all(re.search(DATASHEET_PAGE, citation) for citation in citations):
        raise ValueError("Every rating and test of a verified part must cite a datasheet page")
