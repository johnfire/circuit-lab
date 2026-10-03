"""Numerical intent checks on complete waveforms, before chart downsampling."""

from backend.simulation_models import Check

Waveforms = dict[str, list[tuple[float, float]]]


def evaluate_intent(circuit_id: str, values: dict[str, float],
                    waveforms: Waveforms, ripple_limit: float) -> list[Check]:
    """Select the analytical checks supported by this prototype."""
    if circuit_id == "voltage_divider":
        expected = 5 * values["R2"] / (values["R1"] + values["R2"])
        measured = waveforms["v_out.csv"][-1][1]
        return [Check(name="Divider matches theory", passed=abs(measured - expected) < 0.001,
                      detail=f"At 5 V input: {measured:.4f} V; expected {expected:.4f} V."),
                Check(name="Output fits 3.3 V ADC range", passed=measured <= 3.3,
                      detail=f"Maximum output {measured:.4f} V; allowed ≤ 3.3 V.")]
    if circuit_id == "opamp_noninv":
        expected = min(1 + values["R1"] / values["R2"], 13.5)
        measured = waveforms["v_vout.csv"][-1][1]
        return [Check(name="Amplifier gain matches model", passed=abs(measured - expected) < 0.001,
                      detail=f"At 1 V input: {measured:.4f} V; expected {expected:.4f} V.")]
    if circuit_id == "rc_lowpass":
        return evaluate_rc(values, waveforms["v_out.csv"], ripple_limit)
    if circuit_id == "nand_xspice":
        return evaluate_nand(waveforms)
    return [Check(name="Output changes state", passed=any(
        max(voltage for _, voltage in rows) - min(voltage for _, voltage in rows) > 0.5
        for name, rows in waveforms.items() if name not in {"v_in.csv", "v_lv.csv"}),
        detail="At least one output changes by more than 0.5 V during the simulation.")]


def evaluate_rc(values: dict[str, float], rows: list[tuple[float, float]],
                ripple_limit: float) -> list[Check]:
    """Check settling, mean, and peak-to-peak ripple in the final PWM cycle."""
    time_constant = values["R1"] * values["C1"]
    final_time = rows[-1][0]
    tail_values = [voltage for time, voltage in rows if time >= final_time - 0.001]
    ripple = max(tail_values) - min(tail_values)
    mean = (max(tail_values) + min(tail_values)) / 2
    return [
        Check(name="Enough time to settle", passed=final_time >= 5 * time_constant,
              detail=f"Simulated {final_time * 1000:.1f} ms; 5τ = {5 * time_constant * 1000:.1f} ms."),
        Check(name="PWM average reached", passed=abs(mean - 1.6533) < 0.05,
              detail=f"Final-cycle midpoint {mean:.4f} V; expected approximately 1.653 V."),
        Check(name="Ripple meets target", passed=ripple <= ripple_limit,
              detail=f"Peak-to-peak ripple {ripple:.4f} V; target ≤ {ripple_limit:g} V."),
    ]


def evaluate_nand(waveforms: Waveforms) -> list[Check]:
    """Check the four NAND states after excluding a 10 ns switching window."""
    seen: set[tuple[bool, bool]] = set()
    matches = True
    previous: tuple[bool, bool] | None = None
    changed_at = 0.0
    for (time, a), (_, b), (_, output) in zip(
        waveforms["v_a.csv"], waveforms["v_b.csv"], waveforms["v_out.csv"], strict=True,
    ):
        state = (a > 1.65, b > 1.65)
        if state != previous:
            changed_at, previous = time, state
        if time - changed_at < 10e-9:
            continue
        seen.add(state)
        expected = 0.0 if all(state) else 3.3
        matches = matches and abs(output - expected) < 0.01
    return [Check(name="NAND truth table", passed=matches and len(seen) == 4,
                  detail=f"{len(seen)}/4 stable input states checked against 0/3.3 V NAND output.")]
