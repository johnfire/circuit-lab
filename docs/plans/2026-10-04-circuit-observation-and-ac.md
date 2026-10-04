# Circuit observation and AC — approved design and implementation

Status: Chris approved the grid-first design and implementation on 2026-10-04.
Built and verified locally on main; no push or deployment of this feature yet.
Date: 2026-10-04. Chris explicitly wants both time-domain AC and frequency sweeps
in the first release. The workbench's red, pale-yellow and light-brown palette stays.

## 1. Starting point before this implementation

The deployed analog builder already exports synchronized node-voltage and signed
component-current traces. `schematic-part.tsx` renders those values after a run;
`analog-timeline.tsx` provides a shared time cursor, play/pause, stepping and a viewing
interval. Controls appear below a large grid, making the observation flow unobvious.
The screenshot shows the pre-run state, without readings. There is no sine source,
direction overlay, builder waveform scope or builder frequency-sweep contract yet.

## 2. Recommended layout: grid first

Put Run, Time/Frequency, play/pause, step, speed and the active cursor in a compact
toolbar directly above the grid. Keep the cursor and controls visible while inspecting
the schematic. Fit the circuit to the observation area rather than preserving a large
empty fixed canvas. Keep construction controls available but collapsible in Observe mode.

Place a synchronized scope directly below the grid. Offer scope-beside-grid on wide
screens; on Android always stack the scope below it. These are layouts of the same
results, not separate solvers. The review preview offers both layout alternatives.

Explicit user sequence: Build → Run → Observe. A completed run opens paused at a
useful inspectable instant and makes Play conspicuous; do not auto-start animation.
Explain an all-zero first frame rather than suggesting the simulation failed.
Show Not simulated, Computing, Ready, Stale and Failed distinctly. Never represent
missing data as zero or silently keep old readings after electrical edits.

## 3. Time view: voltages and currents on the schematic

1. Show one labeled node voltage per visible net, referenced to ground, with optional
   extra terminal labels in detailed mode. Keep ground visibly at 0 V.
2. Show voltage across a selected component separately as ΔV = V(terminal 0) −
   V(terminal 1). Do not confuse component voltage with node-to-ground voltage.
3. Show signed current beside each component, defined terminal 0 → 1. Draw a
   conventional-current arrow along its leads; reverse it for negative current.
   Near-zero display thresholds must not change raw measurements or statistics.
4. Optional moving flow markers follow direction and relative magnitude, with a
   bounded visual-speed scale and legend. They illustrate current, not electron
   speed or physical propagation. Reduced-motion mode uses static arrows.
5. Optional voltage shading uses a stable signed scale and legend. Numeric signs
   remain authoritative, so neither polarity nor direction depends on color alone.
6. Pin important measurements so labels do not cover symbols or wires. Automatic
   placement, alternate label anchors, zoom and an accessible measurement list handle
   crowded circuits. All displays use one shared sampled instant.

Animate measured component branches first. The current report contains component
currents, not a unique current for every drawn wire segment. Ideal-wire loops can
have underdetermined segment currents. Do not assign arbitrary flow or infer it from
voltage alone. Simple unambiguous wire chains may get inferred current later, clearly
labeled and verified with Kirchhoff checks; ambiguous segments remain unanimated.

## 4. Time-domain AC and synchronized scope

Add an allow-listed sinusoidal voltage source with offset (V), peak amplitude (V),
frequency (Hz) and phase (degrees), clearly distinguishing peak from RMS. Keep DC
and pulse sources. Start with resistor, RC and RL AC examples; RLC resonance can
provide the bridge to frequency sweeps, using bounded values and real solver output.

Scope probes: tap a node for voltage; tap a component for current; choose two terminals
for differential voltage. Use a separate Probe interaction so tapping does not begin
wiring or move parts. Give every probe a named, styled trace and keyboard equivalent.
Show voltage and current in aligned panes with separate labeled V/A axes and a shared
time cursor. Seeking either plot or the timeline updates grid labels and arrows.

Provide play/pause, sample step, loop and From/Until viewing interval. Add cycle-based
view windows and cycle stepping for a chosen periodic reference source. Distinguish
simulation duration, output sample interval and playback speed. Slow viewing never
changes the source frequency or reruns the solver. Detect inadequate sample density
and recommend a smaller interval; approximately 100 samples per reference cycle is
a starting UI default, not an accuracy guarantee for sharp edges or resonances.

Instantaneous values are the default. RMS, peak-to-peak and mean use a labeled chosen
window and full samples, not downsampled chart points. RMS is total RMS unless the user
explicitly requests its AC-only component. Report phase only for a qualified settled
periodic response and declared reference; otherwise show Not available, not a guessed
number. Startup transients are not mislabeled as steady state. DC bias and initial-state
behavior must be visible; getting a settled window may require a longer real simulation.

## 5. Frequency view: amplitude and phase, not slowed time

Run a genuine ngspice small-signal AC analysis around the DC operating point. Let the
user select one excitation source, its AC amplitude/phase, start/end frequency and
linear/logarithmic spacing. Other sources retain DC bias and have zero AC excitation
by default. Transient SIN parameters and AC excitation are distinct source settings.

Show voltage gain (linear or dB), node/component voltage amplitude, branch-current
amplitude and phase relative to the selected source. Align magnitude and phase plots
on a shared frequency axis, with separate units for volts, amps and dimensionless gain.
The frequency cursor updates amplitude/phase labels on the same schematic. It is not
a time cursor; no moving current-direction animation belongs in this view.

Optional compact phasors for selected probes explain phase relationships; do not
overlay every phasor on the grid. At zero or near-zero amplitude, phase is undefined
and hidden, not fabricated. Undefined gain ratios and logarithms stay explicit gaps.
Use local wrapped phase on schematic labels and an explicitly labeled unwrapped
option on Bode plots. Do not interpolate wrapped angles across the ±180° discontinuity.

Initial proposed sweep bounds: positive ordered frequencies, 1 mHz–1 MHz, maximum
1000 frequency points. Final safe limits must be verified under the existing worker
timeout/resource budgets. Exceeding budgets produces an actionable error; never silently
coarsen the requested analysis. Existing graph limits remain unless separately reviewed.

## 6. Implementation architecture after approval

1. Preserve the existing strict graph input, server-generated netlist, identity-bound
   audit/correlation IDs, two-job budget, no-network worker and timeouts. Add numeric
   sinusoidal and AC source schemas; do not accept expressions, raw SPICE or model text.
2. Keep transient and AC result contracts separate, discriminated by analysis kind.
   Transient results retain shared times and signed real traces. AC results carry shared
   frequencies and complex voltage/current traces as finite real/imaginary arrays, plus
   excitation and DC-bias metadata. Derive amplitude/phase from complex values centrally.
3. Separate circuit model, solver request/result, probes, cursor and display preferences.
   One presentation controller updates grid and scope, never one clock per component.
   Keep pure tested measurement/formatting functions separate from rendering and animation.
4. Preserve full samples for measurements and exports; downsample plots only with
   extrema preservation. Version circuit files so old DC/pulse designs remain importable.
5. Layout-only edits keep valid results; any relevant electrical, excitation or analysis
   setting change invalidates that result. Switching between retained valid Time and
   Frequency results does not unnecessarily rerun simulations.

## 7. Acceptance tests and build order

1. Build the observation toolbar, probe interaction, on-grid labels and branch arrows.
   Test DC sign/reference correctness and RC charging/discharging against real ngspice.
2. Add sine-source input and time scope; verify resistor V/I in phase, capacitor/inductor
   behavior against analytic ideal-circuit expectations in settled windows, current
   reversal, synchronized cursor, RMS/window semantics and sampling warnings.
3. Add genuine AC sweeps and complex-result validation. Verify RC gain/phase/cutoff,
   RL response, selected-source normalization, zero-amplitude phase handling and limits.
4. Exercise the complete Build → Run → Probe → Play/Seek → Frequency flow in browser
   tests. Include Android layout, keyboard operation, reduced motion, label collisions,
   stale reports, export compatibility, worker rejection/isolation and accessibility.
   Never remove or weaken an existing test to accommodate this expansion.

Both AC modes are part of the requested first release; the order above is implementation
sequencing, not permission to omit sweeps. These remain ideal analog models, not a
Raspberry Pi GPIO protection assessment or manufacturer-qualified hardware design.

## 8. Review decisions

Recommended: Grid first by default, optional scope beside grid on wide screens;
signed numeric readings and arrows always available; moving markers and voltage shading
optional. Confirm the preferred layout and whether moving markers should be on by default.
Chris approved implementation. Pushing still requires separate explicit authorization.

Technical reference: [ngspice tutorial: transient and small-signal AC analysis](https://ngspice.sourceforge.io/ngspice-tutorial.html).
The review preview uses an explicitly labeled analytic ideal RC steady-state illustration,
not a substitute for real ngspice results or proof that the proposed feature is implemented.

## 9. Local implementation and verification — 2026-10-04

- Grid-first Observe mode, compact sticky observation toolbar, hidden construction
  controls with a Build toggle, fit bounds and deterministic net-label avoidance of
  symbols, other annotations and orthogonal wires. The synchronized scope is below
  the grid by default; optional beside-grid layout falls back to stacking on mobile.
- Signed conventional-current arrows for measured component branches, optional
  bounded-speed markers, reduced-motion suppression, selected component ΔV and
  optional fixed full-report signed-voltage shading. No invented ideal-wire currents.
- Numeric sine sources, resistive/RC/RL examples, separate V/A scope panes, shared
  time seeking, cycle stepping/windows, full-sample time-weighted mean/total RMS/
  AC-only RMS/peak-to-peak and explicit undersampling guidance.
- Time phase requires at least three cycles, at least 40 samples/cycle, a low-residual
  fit and stable consecutive cycles at one sine frequency. Reference selection is
  explicit; unsuitable or startup windows show unavailable. 100 samples/cycle remains
  a recommended starting point, not an accuracy guarantee. ngspice's internal maximum
  step is one tenth of the uniform output interval to reduce transient phase error.
- Genuine small-signal AC endpoint and allow-listed worker operation, finite complex
  vectors, excitation/DC metadata, amplitude/gain/dB/phase plots, frequency cursor,
  zero-amplitude phase gaps, wrapped grid readings, optional plot unwrapping and
  selected-probe phasor. Log density is requested points per decade; ngspice 47 aligns
  both endpoints. Linear and log sweeps remain bounded to 2–1000 frequency points.
- Each relevant edit invalidates only the affected report; mode switching reuses
  valid reports without rerunning. Version-2 circuit envelopes retain legacy imports.
  Probes/display/sweep choices are session-only; circuit drafts remain browser-only.
- Existing identity/origin checks, no-network/read-only/non-root worker, two shared
  job slots, resource/time limits and correlated actor audit events remain intact.
  New hosted AC authorization and mixed transient/AC concurrency tests are included.

Final local checks: 237 Python tests (84.85% backend/harness coverage), 20 frontend
unit tests and 16 browser tests passed. Lint, strict typing, production build and both
dependency audits passed with zero known vulnerabilities. Existing tests remain
unchanged; erroneous new fixture/locator/theory assertions were corrected, never
skipped or weakened. Python emits one upstream TestClient deprecation warning.
Real local container checks pass all nine recipes, analog transient and AC jobs,
proxy/executable-input rejection and outbound-network blocking.

This is ideal R/C/L simulation, not hardware rating or Raspberry Pi GPIO validation.
The new feature is local only; CI and public deployment await an authorized push.
