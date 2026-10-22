"""Compact engineering values (330, 10k, 4.7uF) as written on schematics, BOMs and PCBs."""


def engineering_value(value: float, unit: str) -> str:
    """330, 10k, 4.7u: the compact form PCB values are written in."""
    for scale, prefix in ((1e6, "M"), (1e3, "k"), (1, ""), (1e-3, "m"), (1e-6, "u"), (1e-9, "n"), (1e-12, "p")):
        if abs(value) >= scale:
            return f"{value / scale:.3g}{prefix}{unit}"
    return f"{value:.3g}{unit}"
