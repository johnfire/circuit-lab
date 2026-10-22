"""Resistors are limited by their package, capacitors by their chosen rating, electrolytics by polarity."""

import pytest
from pydantic import ValidationError

from backend.kicad_export import export_kicad
from backend.passive_ratings import suggested_rating
from backend.schematic_engine import simulate_schematic
from backend.schematic_models import Part, SchematicResponse
from tests.test_schematic_devices import circuit

GROUND = {"id": "G1", "kind": "GND", "value": 0, "x": 16, "y": 20}


def across_source(volts: float, part: dict[str, object]) -> SchematicResponse:
    """One part straight across a DC source."""
    return simulate_schematic(circuit([
        {"id": "VS", "kind": "V", "value": volts, "x": 4, "y": 10, "rotation": 90},
        {"x": 12, "y": 10, "rotation": 90, **part}, GROUND],
        [("VS", 0, str(part["id"]), 0), (str(part["id"]), 1, "G1", 0), ("VS", 1, "G1", 0)],
        stop=0.001, step=1e-5), "passive")


def checks(report: SchematicResponse, part: str) -> dict[str, tuple[float, float, bool]]:
    """(measured, limit, passed) for each rating of one part."""
    return {check.rating: (check.measured, check.limit, check.passed) for check in report.ratings if check.part == part}


def test_resistor_power_limit_follows_its_package() -> None:
    resistor = {"id": "R1", "kind": "R", "value": 120}
    through_hole = checks(across_source(5, resistor), "R1")
    surface = checks(across_source(5, {**resistor, "footprint": "r0805"}), "R1")
    assert through_hole["power_max"] == (pytest.approx(25 / 120, rel=0.01), 0.25, True)
    assert surface["power_max"][1:] == (0.125, False), "0.21 W cooks a 1/8 W 0805"
    assert surface["voltage_max"] == (pytest.approx(5, rel=0.01), 150, True)
    assert checks(across_source(5, {**resistor, "footprint": "axial_half"}), "R1")["power_max"][1] == 0.5


def test_capacitor_checked_only_once_it_has_a_rating_and_otherwise_gets_advice() -> None:
    capacitor = {"id": "C1", "kind": "C", "value": 1e-6}
    unrated = across_source(12, capacitor)
    assert checks(unrated, "C1") == {}
    [advice] = [warning for warning in unrated.warnings if warning.startswith("C1 has no voltage rating")]
    assert "up to 12 V" in advice and "at least 25 V" in advice
    too_low = across_source(12, {**capacitor, "voltage_rating": 10})
    assert checks(too_low, "C1")["voltage_max"] == (pytest.approx(12, rel=0.01), 10, False)
    [rated] = [check for check in across_source(12, {**capacitor, "voltage_rating": 25}).ratings if check.part == "C1"]
    assert rated.passed and rated.trust == "verified", "the user's own rating is not a draft library claim"


def test_reversed_electrolytic_fails_its_polarity_check() -> None:
    electrolytic = {"id": "C1", "kind": "C", "value": 1e-5, "footprint": "radial", "voltage_rating": 25}
    forward = checks(across_source(5, electrolytic), "C1")
    reversed_ = checks(across_source(-5, electrolytic), "C1")
    assert forward["reverse_voltage_max"][2] is True
    assert reversed_["reverse_voltage_max"] == (pytest.approx(5, rel=0.01), 0.5, False)
    assert reversed_["voltage_max"][2] is True, "the magnitude alone looks fine; only polarity catches it"


@pytest.mark.parametrize(("peak", "rating"), [(0, 6.3), (3.3, 6.3), (5, 10), (12, 25), (24, 50), (5000, 1000)])
def test_suggested_rating_is_the_next_standard_voltage_above_one_and_a_half_times(peak: float, rating: float) -> None:
    assert suggested_rating(peak) == rating


def test_only_capacitors_carry_a_voltage_rating() -> None:
    with pytest.raises(ValidationError, match="capacitors only"):
        Part(id="R1", kind="R", value=1e3, x=4, y=4, voltage_rating=50)


def test_kicad_bom_names_the_capacitor_voltage_and_flags_unrated_ones() -> None:
    def supply(rating: float | None) -> list[str]:
        request = circuit([{"id": "VS", "kind": "V", "value": 5, "x": 4, "y": 10, "rotation": 90},
                           {"id": "C1", "kind": "C", "value": 1e-5, "x": 12, "y": 10, "rotation": 90,
                            "footprint": "radial", "voltage_rating": rating}, GROUND],
                          [("VS", 0, "C1", 0), ("C1", 1, "G1", 0), ("VS", 1, "G1", 0)])
        exported = export_kicad(request)
        return [exported.bom_csv, *exported.warnings]
    rated, unrated = supply(16), supply(None)
    assert "10uF 16V" in rated[0] and not any("No voltage rating" in line for line in rated)
    assert any(line.startswith("No voltage rating on C1") for line in unrated)
