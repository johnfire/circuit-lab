"""Limits for resistors and capacitors: package ratings, the chosen capacitor voltage, and advice.

A resistor's power and working voltage come from its PCB package. A capacitor's voltage rating
belongs to the part the user buys, so it is set on the part; without one, the run suggests one.
Electrolytics are polarised (terminal 0 is +), so reverse voltage across them is checked too.
"""

from backend.footprint_catalog import chosen_footprint
from backend.part_library_models import Rating
from backend.schematic_models import Part, Trace

CHOSEN_ON_PART = "chosen on the part (voltage_rating)"
STANDARD_CAPACITOR_VOLTAGES = (6.3, 10, 16, 25, 35, 50, 63, 100, 160, 250, 400, 630, 1000)
CAPACITOR_MARGIN = 1.5


def positive(expression: str) -> str:
    """Elementwise max(x, 0), written with operators ngspice vectors support."""
    return f"(({expression})+abs({expression}))/2"


def passive_limits(part: Part, voltages: list[str], current: str
                   ) -> tuple[str, str, dict[str, tuple[Rating, str]]] | None:
    """(package id, trust, {rating: (limit, expression)}) for a rated resistor or capacitor."""
    if part.kind not in {"R", "C"}:
        return None
    option = chosen_footprint(part.kind, None, part.footprint)
    if option is None:
        return None
    across = f"{voltages[0]}-{voltages[1]}"
    expressions = {"power_max": f"abs(({across})*{current})", "voltage_max": f"abs({across})",
                   "reverse_voltage_max": positive(f"{voltages[1]}-{voltages[0]}")}
    ratings = dict(option.ratings)
    if part.voltage_rating is not None:
        ratings["voltage_max"] = Rating(value=part.voltage_rating, unit="V", source=CHOSEN_ON_PART)
    if not ratings:
        return None
    return f"{part.kind.lower()}_{option.id}", "draft", {
        name: (rating, expressions[name]) for name, rating in ratings.items()}


def suggested_rating(peak: float) -> float:
    """The smallest standard capacitor voltage at least 1.5 times the peak it sees."""
    needed = peak * CAPACITOR_MARGIN
    return next((voltage for voltage in STANDARD_CAPACITOR_VOLTAGES if voltage >= needed),
                STANDARD_CAPACITOR_VOLTAGES[-1])


def capacitor_advice(parts: list[Part], nodes: dict[str, str], traces: list[Trace]) -> list[str]:
    """For each capacitor without a voltage rating, its sampled peak and a rating to choose."""
    voltages = {trace.name.removeprefix("V:"): trace.values for trace in traces if trace.name.startswith("V:")}
    advice = []
    for part in parts:
        if part.kind != "C" or part.voltage_rating is not None:
            continue
        first, second = (voltages.get(nodes[f"{part.id}:{terminal}"]) for terminal in (0, 1))
        frames = len(first or second or [])
        peak = max((abs((first[frame] if first else 0.0) - (second[frame] if second else 0.0))
                    for frame in range(frames)), default=0.0)
        advice.append(f"{part.id} has no voltage rating, so it is not checked. It sees up to {peak:.3g} V in "
                      f"this run: choose at least {suggested_rating(peak):g} V (1.5x the peak; ceramics lose "
                      "capacitance near their rating, so 2x is safer for them).")
    return advice
