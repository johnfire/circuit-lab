"""Numerical intent checks on complete waveforms, before chart downsampling."""

from backend.localization import text
from backend.simulation_models import Check

Waveforms = dict[str, list[tuple[float, float]]]


def evaluate_intent(circuit_id: str, values: dict[str, float],
                    waveforms: Waveforms, ripple_limit: float) -> list[Check]:
    """Select the analytical checks supported by this prototype."""
    if circuit_id == "voltage_divider":
        expected = 5 * values["R2"] / (values["R1"] + values["R2"])
        measured = waveforms["v_out.csv"][-1][1]
        return [Check(name=text('verification_checks.evaluate_intent.divider_matches_theory'), passed=abs(measured - expected) < 0.001,
                      detail=text('verification_checks.evaluate_intent.at_5_v_input_v', measured=f'{measured:.4f}', expected=f'{expected:.4f}')),
                Check(name=text('verification_checks.evaluate_intent.output_fits_3_3_v'), passed=measured <= 3.3,
                      detail=text('verification_checks.evaluate_intent.maximum_output_v_allowed_3', measured=f'{measured:.4f}'))]
    if circuit_id == "opamp_noninv":
        expected = min(1 + values["R1"] / values["R2"], 13.5)
        measured = waveforms["v_vout.csv"][-1][1]
        return [Check(name=text('verification_checks.evaluate_intent.amplifier_gain_matches_model'), passed=abs(measured - expected) < 0.001,
                      detail=text('verification_checks.evaluate_intent.at_1_v_input_v', measured=f'{measured:.4f}', expected=f'{expected:.4f}'))]
    if circuit_id == "rc_lowpass":
        return evaluate_rc(values, waveforms["v_out.csv"], ripple_limit)
    if circuit_id == "nand_xspice":
        return evaluate_nand(waveforms)
    return [Check(name=text('verification_checks.evaluate_intent.output_changes_state'), passed=any(
        max(voltage for _, voltage in rows) - min(voltage for _, voltage in rows) > 0.5
        for name, rows in waveforms.items() if name not in {"v_in.csv", "v_lv.csv"}),
        detail=text('verification_checks.evaluate_intent.at_least_one_output_changes'))]


def evaluate_rc(values: dict[str, float], rows: list[tuple[float, float]],
                ripple_limit: float) -> list[Check]:
    """Check settling, mean, and peak-to-peak ripple in the final PWM cycle."""
    time_constant = values["R1"] * values["C1"]
    final_time = rows[-1][0]
    tail_values = [voltage for time, voltage in rows if time >= final_time - 0.001]
    ripple = max(tail_values) - min(tail_values)
    mean = (max(tail_values) + min(tail_values)) / 2
    return [
        Check(name=text('verification_checks.evaluate_rc.enough_time_to_settle'), passed=final_time >= 5 * time_constant,
              detail=text('verification_checks.evaluate_rc.simulated_ms_5_ms', duration=f'{final_time * 1000:.1f}', settling=f'{5 * time_constant * 1000:.1f}')),
        Check(name=text('verification_checks.evaluate_rc.pwm_average_reached'), passed=abs(mean - 1.6533) < 0.05,
              detail=text('verification_checks.evaluate_rc.final_cycle_midpoint_v_expected', mean=f'{mean:.4f}')),
        Check(name=text('verification_checks.evaluate_rc.ripple_meets_target'), passed=ripple <= ripple_limit,
              detail=text('verification_checks.evaluate_rc.peak_to_peak_ripple_v', ripple=f'{ripple:.4f}', target=f'{ripple_limit:g}')),
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
    return [Check(name=text('verification_checks.evaluate_nand.nand_truth_table'), passed=matches and len(seen) == 4,
                  detail=text('verification_checks.evaluate_nand.4_stable_input_states_checked', states=len(seen)))]
