"""Curated examples and their editable passive components."""

import re
from pathlib import Path

from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
SUFFIXES = {"": 1.0, "k": 1e3, "meg": 1e6, "m": 1e-3, "u": 1e-6, "n": 1e-9, "p": 1e-12}
DESCRIPTIONS = {
    "voltage_divider": ("Sensor voltage divider", "Scale a 0–5 V sensor signal with two resistors."),
    "rc_lowpass": ("PWM to analog", "Smooth a 3.3 V, 1 kHz PWM signal into an analog voltage."),
    "mosfet_switch": ("MOSFET load switch", "Switch a resistive 12 V load from a 3.3 V GPIO."),
    "led_driver": ("GPIO LED driver", "Explore LED current limiting with a series resistor."),
    "level_shifter_bss138": ("Bidirectional level shifter", "Explore a generic MOSFET level-shifter model."),
    "opamp_noninv": ("Non-inverting amplifier", "Set the gain of an ideal, rail-limited amplifier."),
    "debounce_rc": ("Button debounce", "Filter a pulse with an RC network and threshold comparator."),
    "inverter_behavioral": ("Logic inverter", "Invert a 3.3 V input with a behavioral threshold."),
    "nand_xspice": ("NAND gate", "Mixed-signal NAND with explicit analog/digital bridges."),
}


class Parameter(BaseModel):
    """Editable value in SI units with safe numerical bounds."""

    name: str
    value: float
    unit: str
    minimum: float
    maximum: float


class Component(BaseModel):
    """A component and its node connectivity, derived from the netlist."""

    name: str
    kind: str
    nodes: list[str]
    value: str


class Circuit(BaseModel):
    """A curated simulation recipe, not a human-verified physical part."""

    id: str
    title: str
    description: str
    category: str
    parameters: list[Parameter]
    components: list[Component]
    model_trust: str = "generic"


def parse_spice_number(value: str) -> float:
    """Convert the example library's SPICE suffixes to SI units."""
    match = re.fullmatch(r"(\d+(?:\.\d*)?(?:[eE][-+]?\d+)?)(meg|[kmunp])?", value)
    if not match:
        raise ValueError(f"Unsupported component value: {value}")
    return float(match[1]) * SUFFIXES[match[2] or ""]


def read_components(netlist: str) -> list[Component]:
    """Extract supported component connectivity without executing any input."""
    components = []
    for line in netlist.splitlines():
        if line.strip().lower() == ".control":
            break
        tokens = line.split()
        if not tokens or tokens[0][0].upper() not in "RCLVDMB":
            continue
        kind = tokens[0][0].upper()
        node_count = 4 if kind == "M" else 2
        if len(tokens) < node_count + 2:
            continue
        components.append(Component(
            name=tokens[0], kind=kind, nodes=tokens[1:node_count + 1],
            value=" ".join(tokens[node_count + 1:]),
        ))
    return components


def read_circuit(circuit_id: str) -> Circuit:
    """Resolve only registered example IDs and describe their parameters."""
    if circuit_id not in DESCRIPTIONS:
        raise ValueError("Unknown circuit")
    matches = list((ROOT / "circuits").glob(f"*/{circuit_id}.cir"))
    if len(matches) != 1:
        raise ValueError("Circuit unavailable")
    components = read_components(matches[0].read_text())
    parameters = [
        Parameter(name=part.name, value=parse_spice_number(part.value), unit="Ω" if part.kind == "R" else "F",
                  minimum=1 if part.kind == "R" else 1e-12, maximum=1e6 if part.kind == "R" else 1e-3)
        for part in components if part.kind in "RC"
    ]
    title, description = DESCRIPTIONS[circuit_id]
    return Circuit(id=circuit_id, title=title, description=description,
                   category=matches[0].parent.name, parameters=parameters, components=components)


def list_circuits() -> list[Circuit]:
    """Return the complete curated catalog in a stable order."""
    return [read_circuit(circuit_id) for circuit_id in DESCRIPTIONS]


def read_netlist(circuit_id: str) -> str:
    """Load the trusted recipe for a previously validated circuit ID."""
    read_circuit(circuit_id)
    return next((ROOT / "circuits").glob(f"*/{circuit_id}.cir")).read_text()
