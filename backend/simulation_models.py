"""Validated request and response contracts for the simulation boundary."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.localization import LocalizationMetadata, LocalizedString, LocalizedText

NumericValue = Annotated[float, Field(gt=0, le=1e9, allow_inf_nan=False)]


class SimulationRequest(BaseModel):
    """Only numerical component edits are accepted; raw SPICE is never accepted."""

    model_config = ConfigDict(extra="forbid")
    parameters: dict[str, NumericValue] = Field(default_factory=dict, max_length=20)
    max_ripple_v: NumericValue = 0.15


class Signal(BaseModel):
    """A waveform with full-resolution summary and bounded chart samples."""

    name: str
    points: list[tuple[float, float]]
    minimum: float
    maximum: float
    final: float
    sample_count: int


class Check(BaseModel):
    """An explicit numerical check, including an explanation of its scope."""

    name: str
    passed: bool
    detail: str
    name_message: LocalizedText | None = None
    detail_message: LocalizedText | None = None

    @model_validator(mode="before")
    @classmethod
    def capture_messages(cls, submitted: object) -> object:
        if not isinstance(submitted, dict):
            return submitted
        captured = dict(submitted)
        for field in ("name", "detail"):
            original = captured.get(field)
            if isinstance(original, LocalizedString):
                captured[field + "_message"] = original.reference
        return captured


class SimulationResponse(LocalizationMetadata):
    """A simulation report that never certifies a physical circuit."""

    circuit_id: str
    correlation_id: str
    status: str
    model_trust: str = "generic"
    parameters: dict[str, float]
    signals: list[Signal]
    checks: list[Check]
    warnings: list[str]
    netlist: str
    duration_ms: float
