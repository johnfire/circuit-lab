"""Behavioral subcircuits generated from a library part's validated numeric parameters.

Op-amp: one transconductance stage into an RC dominant pole (open-loop gain and gain-bandwidth),
its current limited by tanh to set the slew rate, and a smooth high-conductance pull-back holding
the internal node within the output swing. Every limit is smooth: hard min/max clipping made
ngspice's operating-point search fail, and near-ideal (N=0.05) clamp diodes let it accept a falsely
converged operating point at the rail. Output current is drawn from the matching supply pin.

Linear regulator: V(out) - V(ref) = min(VREG, V(in) - V(ref) - DROPOUT), never negative. The load
current is drawn from the input, and IQ flows out of the ground/adjust pin.
"""

import math

POLE_CAPACITANCE = 1e-9
CLAMP_CONDUCTANCE = 10


def number(value: float) -> str:
    """A full-precision SPICE literal."""
    return f"{value:.12g}"


def smooth_positive(expression: str, rounding: float = 1e-9) -> str:
    """max(x, 0) without a corner at zero; the corner is rounded over about `rounding`."""
    return f"(({expression})+sqrt(({expression})*({expression})+{number(rounding * rounding)}))/2"


def opamp_subcircuit(name: str, parameters: dict[str, float]) -> list[str]:
    """Ports: output, in_plus, in_minus, v_plus, v_minus."""
    gain, bandwidth = parameters["AOL"], parameters["GBW"]
    transconductance = 2 * math.pi * bandwidth * POLE_CAPACITANCE
    resistance = gain / transconductance
    slew_current = parameters["SR"] * POLE_CAPACITANCE
    offset, high_drop, low_drop = parameters["VOS"], parameters["VOHDROP"], parameters["VOLDROP"]
    return [
        f".subckt {name} out inp inn vp vn",
        f"Rin inp inn {number(parameters['RIN'])}",
        f"Iq vp vn {number(parameters['ISUP'])}",
        f"Bgain 0 n1 I = {number(slew_current)}*tanh({number(transconductance / slew_current)}"
        f"*(V(inp,inn)+{number(offset)}))",
        f"Rgain n1 0 {number(resistance)}",
        f"Cpole n1 0 {number(POLE_CAPACITANCE)}",
        f"Bhigh hi 0 V = V(vp)-{number(high_drop)}",
        f"Blow lo 0 V = V(vn)+{number(low_drop)}",
        f"Bclamp 0 n1 I = -{number(CLAMP_CONDUCTANCE)}*({smooth_positive('V(n1)-V(hi)', 1e-6)}"
        f" - {smooth_positive('V(lo)-V(n1)', 1e-6)})",
        "Ebuffer o2 0 n1 0 1",
        "Vsense o2 o3 0",
        f"Rout o3 out {number(parameters['ROUT'])}",
        f"Bsource vp 0 I = {smooth_positive('i(Vsense)')}",
        f"Bsink 0 vn I = {smooth_positive('-i(Vsense)')}",
        ".ends",
    ]


def regulator_subcircuit(name: str, parameters: dict[str, float]) -> list[str]:
    """Ports: output, input, ground_or_adjust."""
    return [
        f".subckt {name} out in ref",
        f"Iq in ref {number(parameters['IQ'])}",
        f"Bpass x ref V = max(min({number(parameters['VREG'])}, "
        f"V(in,ref)-{number(parameters['DROPOUT'])}), 0)",
        "Vsense x out 0",
        "Fsupply in ref Vsense 1",
        ".ends",
    ]


SUBCIRCUITS = {"OPAMP": opamp_subcircuit, "REG": regulator_subcircuit}
