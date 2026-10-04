"""Bounded queries and numerical evidence on full, revision-bound solver samples."""

import math
from typing import Literal, Self

from pydantic import Field, model_validator

from backend.project_models import ProjectFailure
from backend.schematic_ac_models import ACResponse
from backend.schematic_models import Finite, Pin, SchematicResponse, StrictModel

Report = SchematicResponse | ACResponse


class SignalQuery(StrictModel):
    """Choose a branch current, node voltage or signed differential voltage."""

    kind: Literal["node", "current", "differential"]
    first: Pin
    second: Pin | None = None

    @model_validator(mode="after")
    def validate_second_pin(self) -> Self:
        """Differential voltage needs two terminals and nothing else does."""
        if (self.kind == "differential") != (self.second is not None):
            raise ValueError("A second pin is required only for differential voltage")
        return self


class SampleQuery(StrictModel):
    """Retrieve at most 256 full-precision solver samples per bounded page."""

    signal: SignalQuery
    offset: int = Field(default=0, strict=True, ge=0, le=2002)
    limit: int = Field(default=128, strict=True, ge=1, le=256)


class MeasurementQuery(StrictModel):
    """A physical axis interval, not array positions or an executable formula."""

    signal: SignalQuery
    start: Finite = Field(ge=0)
    stop: Finite = Field(gt=0)

    @model_validator(mode="after")
    def validate_interval(self) -> Self:
        """Reject reversed or empty viewing windows before reading samples."""
        if self.stop <= self.start:
            raise ValueError("Measurement window end must exceed start")
        return self


class IntentCheck(StrictModel):
    """A declarative unit-checked predicate, never a code/expression evaluator."""

    query: MeasurementQuery
    metric: Literal["minimum", "maximum", "mean", "rms", "ac_rms", "peak_to_peak", "final"]
    unit: Literal["V", "A"]
    comparison: Literal["less_equal", "greater_equal"]
    threshold: Finite


def axis(report: Report) -> list[float]:
    """Return the one shared physical axis for this report."""
    return report.frequencies if isinstance(report, ACResponse) else report.times


def pin_voltage(report: Report, pin: Pin) -> tuple[list[float], list[float]]:
    """Resolve a stable pin against this exact report's revision-local net map."""
    node = report.pin_nodes.get(f"{pin.part}:{pin.terminal}")
    if node is None:
        raise ProjectFailure("Pin is absent from this simulation")
    if node == "0":
        zeros = [0.0] * len(axis(report))
        return zeros, zeros
    return named_signal(report, f"V:{node}")[1:]


def named_signal(report: Report, name: str) -> tuple[str, list[float], list[float]]:
    """Do not invent a missing current or voltage trace."""
    matches = [trace for trace in report.traces if trace.name == name]
    if not matches:
        raise ProjectFailure("Signal is absent from this simulation")
    trace = matches[0]
    if isinstance(report, ACResponse):
        trace = next(signal for signal in report.traces if signal.name == name)
        return trace.unit, trace.real, trace.imaginary
    trace = next(signal for signal in report.traces if signal.name == name)
    return trace.unit, trace.values, [0.0] * len(trace.values)


def resolve_signal(report: Report, query: SignalQuery) -> tuple[str, list[float], list[float]]:
    """Current is 0->1; differential voltage is first minus second."""
    if query.kind == "current":
        return named_signal(report, f"I:{query.first.part}")
    real, imaginary = pin_voltage(report, query.first)
    if query.second is not None:
        other_real, other_imaginary = pin_voltage(report, query.second)
        real = [first - second for first, second in zip(real, other_real, strict=True)]
        imaginary = [first - second for first, second in zip(imaginary, other_imaginary, strict=True)]
    return "V", real, imaginary


def sample_page(report: Report, query: SampleQuery) -> dict[str, object]:
    """Return original samples, with explicit page and analysis semantics."""
    unit, real, imaginary = resolve_signal(report, query.signal)
    positions = slice(query.offset, query.offset + query.limit)
    shared_axis = axis(report)
    response: dict[str, object] = {"analysis": "ac" if isinstance(report, ACResponse) else "transient",
        "unit": unit, "axis_unit": "Hz" if isinstance(report, ACResponse) else "s",
        "axis": shared_axis[positions], "real": real[positions], "decimated": False,
        "total_samples": len(shared_axis), "next_offset": None}
    if query.offset + query.limit < len(shared_axis):
        response["next_offset"] = query.offset + query.limit
    if isinstance(report, ACResponse):
        response["imaginary"] = imaginary[positions]
    return response


def time_statistics(times: list[float], values: list[float]) -> dict[str, float]:
    """Time-weighted trapezoidal statistics match the browser's full-sample method."""
    validate_time_samples(times, values)
    duration = times[-1] - times[0]
    area = sum((second_time - first_time) * (first + second) / 2
               for first_time, second_time, first, second in
               zip(times, times[1:], values, values[1:], strict=False))
    squared = sum((second_time - first_time) * (first * first + second * second) / 2
                  for first_time, second_time, first, second in
                  zip(times, times[1:], values, values[1:], strict=False))
    mean = area / duration
    rms = math.sqrt(max(0, squared / duration))
    return {"minimum": min(values), "maximum": max(values), "mean": mean, "rms": rms,
            "ac_rms": math.sqrt(max(0, rms * rms - mean * mean)),
            "peak_to_peak": max(values) - min(values), "final": values[-1]}


def validate_time_samples(times: list[float], values: list[float]) -> None:
    """Reject truncated, non-finite or unordered evidence instead of calculating it."""
    if len(times) < 2 or len(times) != len(values):
        raise ProjectFailure("Statistics require matching arrays with at least two samples")
    if not all(math.isfinite(value) for value in [*times, *values]):
        raise ProjectFailure("Statistics require finite samples")
    if any(second <= first for first, second in zip(times, times[1:])):
        raise ProjectFailure("Statistics require strictly increasing times")


def measure(report: Report, query: MeasurementQuery) -> dict[str, object]:
    """AC magnitude summaries never masquerade as time statistics or transient RMS."""
    unit, real, imaginary = resolve_signal(report, query.signal)
    indices = [index for index, value in enumerate(axis(report)) if query.start <= value <= query.stop]
    if len(indices) < 2:
        return {"status": "unavailable", "reason": "At least two solver samples are needed"}
    if isinstance(report, ACResponse):
        samples = [math.hypot(real[index], imaginary[index]) for index in indices]
        phases = [None if samples[position] < 1e-12 else
                  ((math.degrees(math.atan2(imaginary[index], real[index])) -
                    report.excitation.phase + 180) % 360 - 180)
                  for position, index in enumerate(indices)]
        return {"status": "completed", "analysis": "ac", "unit": unit,
                "samples": len(indices), "minimum_amplitude": min(samples),
                "actual_window": [report.frequencies[indices[0]], report.frequencies[indices[-1]]],
                "axis_unit": "Hz",
                "maximum_amplitude": max(samples), "phase_reference": "AC excitation",
                "first_phase_degrees": phases[0], "last_phase_degrees": phases[-1],
                "gain_minimum": min(samples) / report.excitation.amplitude if unit == "V" else None,
                "gain_maximum": max(samples) / report.excitation.amplitude if unit == "V" else None}
    statistics = time_statistics([report.times[index] for index in indices], [real[index] for index in indices])
    return {"status": "completed", "analysis": "transient", "unit": unit,
            "samples": len(indices), "method": "full-sample time-weighted trapezoidal",
            "actual_window": [report.times[indices[0]], report.times[indices[-1]]], **statistics}


def evaluate_check(report: Report, check: IntentCheck) -> dict[str, object]:
    """Return numerical pass/fail/unavailable evidence, not an LLM verdict."""
    measurement = measure(report, check.query)
    if measurement.get("status") != "completed" or isinstance(report, ACResponse):
        return {"status": "unavailable", "reason": "This metric requires a sampled transient window"}
    if check.unit != measurement["unit"]:
        raise ProjectFailure("Check unit does not match the signal's physical unit")
    coefficient = measurement[check.metric]
    if not isinstance(coefficient, (int, float)):
        raise ProjectFailure("Metric is unavailable")
    passed = coefficient <= check.threshold if check.comparison == "less_equal" else coefficient >= check.threshold
    return {"status": "pass" if passed else "fail", "measured": coefficient,
            "threshold": check.threshold, "comparison": check.comparison, "unit": check.unit,
            "metric": check.metric, "window": measurement["actual_window"]}
