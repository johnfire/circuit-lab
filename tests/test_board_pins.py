"""Development boards: pinout data, pin validation, and pin protection checks on ngspice."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.board_library import BOARDS, board_summaries, load_boards
from backend.board_models import Board
from backend.schematic_ac_engine import simulate_ac
from backend.schematic_ac_models import ACRequest
from backend.schematic_engine import simulate_schematic
from backend.schematic_models import Part, SchematicResponse
from tests.test_schematic_devices import circuit, ratings_by_name

GROUND = {"id": "G1", "kind": "GND", "value": 0, "x": 16, "y": 20}


def board_pin(mode: str, pin: str = "11", board: str = "raspberry_pi_4", part_id: str = "P1",
              **extra: object) -> dict[str, object]:
    """A placed board pin; pin 11 of a Pi header is GPIO17."""
    return {"id": part_id, "kind": "PIN", "value": 0, "x": 4, "y": 10,
            "board_pin": {"board": board, "pin": pin, "mode": mode}, **extra}


def pin_voltage(report: SchematicResponse, pin: str = "P1:0") -> float:
    """Settled voltage at a terminal."""
    node = report.pin_nodes[pin]
    return next(trace for trace in report.traces if trace.name == f"V:{node}").values[-1]


def test_pi_headers_are_the_standard_40_pin_layout() -> None:
    for board_id in ("raspberry_pi_4", "raspberry_pi_5"):
        board = BOARDS[board_id]
        names = {pin.id: pin.name for pin in board.pins}
        assert len(board.pins) == 40
        assert sorted(pin.gpio for pin in board.pins if pin.gpio is not None) == list(range(28))
        assert [pin.id for pin in board.pins if pin.kind == "ground"] == ["6", "9", "14", "20", "25", "30", "34", "39"]
        assert (names["1"], names["2"], names["11"], names["12"], names["40"]) == (
            "3V3", "5V", "GPIO17", "GPIO18", "GPIO21")
        assert board.pin("3") is not None and board.pin("3").fixed_pull_up == 1800
    assert {board["id"] for board in board_summaries()} >= {
        "raspberry_pi_4", "raspberry_pi_5", "arduino_uno_r3", "raspberry_pi_pico", "esp32_devkitc"}


def led_from_gpio(resistance: float) -> SchematicResponse:
    """Pi GPIO17 high → series resistor → red LED → ground."""
    return simulate_schematic(circuit([
        board_pin("output_high"), {"id": "R1", "kind": "R", "value": resistance, "x": 10, "y": 8},
        {"id": "D1", "kind": "D", "device": "led_red_5mm", "value": 0, "x": 16, "y": 10, "rotation": 90},
        GROUND], [("P1", 0, "R1", 0), ("R1", 1, "D1", 0), ("D1", 1, "G1", 0)],
        stop=0.001, step=1e-5), "led")


def test_gpio_drives_an_led_through_its_output_resistance_and_current_limit() -> None:
    safe = led_from_gpio(330)
    current = ratings_by_name(safe)[("P1", "pin_current_max")]
    led_voltage = pin_voltage(safe, "D1:0")
    assert 1.7 < led_voltage < 2.0, "a red LED at a few mA drops a little under its 20 mA rating"
    assert current == pytest.approx((3.3 - led_voltage) / (330 + 75), rel=0.01)
    assert all(check.passed for check in safe.ratings)
    shorted = led_from_gpio(1)
    [pin_current] = [check for check in shorted.ratings if check.rating == "pin_current_max"]
    assert not pin_current.passed and pin_current.limit == 0.016


def five_volts_into_input(divider: bool) -> SchematicResponse:
    """A 5 V signal into Pi GPIO17 through 1 kΩ, or through a 10k/20k divider."""
    parts = [board_pin("input"), {"id": "VS", "kind": "V", "value": 5, "x": 26, "y": 10, "rotation": 90},
             GROUND, {"id": "R1", "kind": "R", "value": 10000 if divider else 1000, "x": 16, "y": 8}]
    wires = [("VS", 0, "R1", 0), ("R1", 1, "P1", 0), ("VS", 1, "G1", 0)]
    if divider:
        parts.append({"id": "R2", "kind": "R", "value": 20000, "x": 10, "y": 14, "rotation": 90})
        wires += [("R2", 0, "P1", 0), ("R2", 1, "G1", 0)]
    return simulate_schematic(circuit(parts, wires, stop=0.001, step=1e-5), "five-volt")


def test_five_volts_into_a_pi_pin_fails_and_a_divider_fixes_it() -> None:
    raw = five_volts_into_input(divider=False)
    [overvoltage] = [check for check in raw.ratings if check.rating == "pin_voltage_max"]
    assert not overvoltage.passed
    assert 3.8 < pin_voltage(raw) < 4.1, "the ESD clamp diode holds the pin about 0.6 V above 3.3 V"
    divided = five_volts_into_input(divider=True)
    assert pin_voltage(divided) == pytest.approx(5 * 20 / 30, abs=0.01)
    assert all(check.passed for check in divided.ratings)


def test_supply_pin_budget_and_fixed_i2c_pull_up() -> None:
    for load, passes in ((10, True), (5, False)):
        report = simulate_schematic(circuit([board_pin("supply", "1"),
            {"id": "RL", "kind": "R", "value": load, "x": 12, "y": 10, "rotation": 90}, GROUND],
            [("P1", 0, "RL", 0), ("RL", 1, "G1", 0)], stop=0.001, step=1e-5), "rail")
        [budget] = report.ratings
        assert budget.rating == "supply_current_max" and budget.passed is passes
        assert budget.measured == pytest.approx(3.3 / load, rel=0.01)
    pulled = simulate_schematic(circuit([board_pin("input", "3"),
        {"id": "R1", "kind": "R", "value": 1e6, "x": 12, "y": 10, "rotation": 90}, GROUND],
        [("P1", 0, "R1", 0), ("R1", 1, "G1", 0)], stop=0.001, step=1e-5), "i2c")
    assert pin_voltage(pulled) == pytest.approx(3.3 * 1e6 / (1e6 + 1800), abs=0.01)


def test_pulse_mode_toggles_and_arduino_pins_run_at_5_volts() -> None:
    pulsed = simulate_schematic(circuit([
        board_pin("pulse", pulse={"period": 0.002, "width": 0.001, "delay": 0}),
        {"id": "R1", "kind": "R", "value": 10000, "x": 12, "y": 10, "rotation": 90}, GROUND],
        [("P1", 0, "R1", 0), ("R1", 1, "G1", 0)], stop=0.004, step=2e-5), "pwm")
    values = next(trace for trace in pulsed.traces if trace.name == "V:" + pulsed.pin_nodes["P1:0"]).values
    assert max(values) == pytest.approx(3.3 * 10000 / 10075, abs=0.02) and min(values) < 0.01
    uno = simulate_schematic(circuit([board_pin("output_high", "D13", "arduino_uno_r3"),
        {"id": "R1", "kind": "R", "value": 10000, "x": 12, "y": 10, "rotation": 90}, GROUND],
        [("P1", 0, "R1", 0), ("R1", 1, "G1", 0)], stop=0.001, step=1e-5), "uno")
    assert pin_voltage(uno) == pytest.approx(5 * 10000 / 10040, abs=0.02)


def test_ac_analysis_treats_pins_as_their_dc_levels() -> None:
    biased = circuit([board_pin("output_high"),
        {"id": "VIN", "kind": "V", "value": 0, "x": 26, "y": 10, "rotation": 90},
        {"id": "R1", "kind": "R", "value": 1000, "x": 12, "y": 8},
        {"id": "C1", "kind": "C", "value": 1e-6, "x": 18, "y": 12, "rotation": 90}, GROUND],
        [("P1", 0, "R1", 0), ("R1", 1, "C1", 0), ("C1", 1, "VIN", 0), ("VIN", 1, "G1", 0)])
    report = simulate_ac(ACRequest.model_validate({"circuit": biased.model_dump(), "sweep": {
        "source": "VIN", "amplitude": 1, "phase": 0, "start": 10, "stop": 1000,
        "spacing": "log", "points": 3}}), "pin-ac")
    assert "Vdrive0 d0 0 DC 3.3" in report.netlist


@pytest.mark.parametrize("settings, message", [
    ({"board": "made_up_board", "pin": "11", "mode": "output_high"}, "Unknown board"),
    ({"board": "raspberry_pi_4", "pin": "41", "mode": "output_high"}, "has no pin 41"),
    ({"board": "raspberry_pi_4", "pin": "6", "mode": "input"}, "use the Ground symbol"),
    ({"board": "raspberry_pi_4", "pin": "1", "mode": "output_high"}, "cannot be output_high"),
    ({"board": "raspberry_pi_4", "pin": "11", "mode": "supply"}, "cannot be supply"),
    ({"board": "esp32_devkitc", "pin": "J2-5", "mode": "output_high"}, "cannot be output_high"),
    ({"board": "raspberry_pi_4", "pin": "11", "mode": "pulse"}, "Pulse settings"),
])
def test_board_pin_settings_are_validated(settings: dict[str, str], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        Part.model_validate({"id": "P1", "kind": "PIN", "value": 0, "x": 4, "y": 4, "board_pin": settings})


def test_board_files_reject_duplicates_and_unreviewed_verification(tmp_path: Path) -> None:
    definition = json.loads((Path("circuits/boards/raspberry_pi_4/board.json")).read_text())
    duplicated = {**definition, "pins": [*definition["pins"], definition["pins"][0]]}
    with pytest.raises(ValidationError, match="unique"):
        Board.model_validate(duplicated)
    with pytest.raises(ValidationError, match="who reviewed"):
        Board.model_validate({**definition, "trust": {"level": "verified"}})
    folder = tmp_path / "wrong_folder"
    folder.mkdir()
    (folder / "board.json").write_text(json.dumps(definition))
    with pytest.raises(ValueError, match="folder named raspberry_pi_4"):
        load_boards(tmp_path)
