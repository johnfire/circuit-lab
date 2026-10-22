"""Netlist lines for development-board pins: drive, pulls and ESD clamps at default settings.

A pin is referenced to circuit ground, because the board's GND is the circuit's ground. Outputs
are a source behind the pin's output resistance; inputs are high impedance; every GPIO has clamp
diodes to its logic rail and to ground, so overdriving a pin shows the clamp current that flows.
Power pins are ideal supplies whose current is checked against the pin's budget.
"""

from backend.board_library import BOARDS
from backend.board_models import Board, HeaderPin
from backend.schematic_models import Part

CLAMP_MODEL = ".model lib_pin_clamp D(IS=1e-14 N=1)"
INPUT_LEAKAGE_RESISTANCE = 1e9


def number(value: float) -> str:
    """A full-precision SPICE literal."""
    return f"{value:.12g}"


def pin_of(part: Part) -> tuple[Board, HeaderPin]:
    """The board and header pin a validated PIN part refers to."""
    if part.board_pin is None:
        raise ValueError(f"{part.id} is not a board pin")
    board = BOARDS[part.board_pin.board]
    header_pin = board.pin(part.board_pin.pin)
    if header_pin is None:
        raise ValueError(f"{part.id} names a missing pin")
    return board, header_pin


def driver(part: Part, index: int, logic: float, step: float, analysis: str) -> str:
    """The output driver source: a fixed level, or a pulse train in transient analysis."""
    mode = part.board_pin.mode if part.board_pin else "output_low"
    if mode == "pulse" and part.pulse and analysis == "transient":
        pulse = part.pulse
        edge = min(step / 10, pulse.width / 10, (pulse.period - pulse.width) / 10)
        level = (f"PULSE(0 {number(logic)} {number(pulse.delay)} {number(edge)} {number(edge)} "
                 f"{number(pulse.width)} {number(pulse.period)})")
    else:
        level = f"DC {number(logic if mode == 'output_high' else 0.0)}"
    return f"Vdrive{index} d{index} 0 {level}"


def pin_lines(part: Part, index: int, nodes: dict[str, str], step: float,
              analysis: str = "transient") -> list[str]:
    """Probe the current into the pin, then model what sits behind it on the board."""
    board, header_pin = pin_of(part)
    mode = part.board_pin.mode if part.board_pin else "input"
    internal, electrical = f"p{index}", board.electrical
    lines = [f"Vprobe{index} {nodes[f'{part.id}:0']} {internal} 0"]
    if mode == "supply" and header_pin.voltage is not None:
        return lines + [f"Vsupply{index} {internal} 0 DC {number(header_pin.voltage)}"]
    rail = f"rail{index}"
    lines += [f"Vrail{index} {rail} 0 DC {number(electrical.logic_voltage)}",
              f"Dclamp_high{index} {internal} {rail} lib_pin_clamp",
              f"Dclamp_low{index} 0 {internal} lib_pin_clamp",
              f"Rleak{index} {internal} 0 {number(INPUT_LEAKAGE_RESISTANCE)}"]
    if mode in {"output_high", "output_low", "pulse"}:
        lines += [driver(part, index, electrical.logic_voltage, step, analysis),
                  f"Rdrive{index} d{index} {internal} {number(electrical.output_resistance)}"]
    if mode == "input_pull_up":
        lines.append(f"Rpull{index} {internal} {rail} {number(electrical.pull_resistance)}")
    if mode == "input_pull_down":
        lines.append(f"Rpull{index} {internal} 0 {number(electrical.pull_resistance)}")
    if header_pin.fixed_pull_up is not None:
        lines.append(f"Rboard_pull{index} {internal} {rail} {number(header_pin.fixed_pull_up)}")
    return lines


def pin_model_cards(parts: list[Part]) -> list[str]:
    """The shared ESD clamp diode model, once, if any board GPIO is in the circuit."""
    uses_clamps = any(part.board_pin is not None and part.board_pin.mode != "supply" for part in parts)
    return [CLAMP_MODEL] if uses_clamps else []
