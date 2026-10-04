# Circuit Lab prototype — 2026-10-04

## Built and locally verified

- React/TypeScript browser workbench, responsive desktop/mobile layout.
- Nine curated analog/digital examples, with numeric R/C editing and reset.
- Real ngspice output, extrema-preserving charts, zoom, cursor, and full-sample
  min/max/final statistics. Exported plotted points may be downsampled;
  reported statistics and numerical checks use full simulation output.
- Divider theory and 3.3 V ADC range, PWM filter settling/ripple, ideal amplifier
  gain, and all four NAND input combinations. Other recipes currently have only
  successful-simulation and output-transition checks, not full intent checks.
- Check failures remain visible; editing marks old results stale. Worker errors
  do not prevent the next run or break catalog/health access.
- Supported-component connectivity table, source netlist, and JSON report export.
- Analog schematic editor alongside Examples: R/C/L, DC/pulse sources, ground,
  standard/custom values, snap-to-grid placement, drag/move/rotate, explicit wiring,
  and account-scoped browser drafts plus circuit import/export.
- Real custom analog transient simulation with synchronized terminal voltages and
  signed branch currents on the grid. Scrub, step, slow playback, loop and select
  a viewing interval independently of the solver output interval.
- Grid-first observation toolbar and scope, node/probe labels, selected-component ΔV,
  conventional-current reversal arrows, optional flow markers and stable voltage shading.
- Sine sources and resistor/RC/RL AC examples, time-window RMS/mean/peak-to-peak,
  qualified settled phase, cycle windows and explicit sampling-density warnings.
- Genuine small-signal AC sweeps with complex traces, excitation/DC-bias metadata,
  voltage/current amplitude, gain/dB/phase plots, a synchronized frequency cursor,
  optional phase unwrapping and selected-probe phasor.
- Curated-recipe and validated structured-analog APIs, strict numeric limits, local origin/host restrictions, CSP,
  bounded worker processes, job timeouts, correlation IDs, and local audit records.
- Python unit/integration regressions, real-engine tests for every example,
  browser interaction/export tests, and desktop/mobile axe accessibility checks.
- Locked dependencies; main-branch CI and dependency scanning configuration.
- Public early-preview landing page with signup/sign-in and Rehm Consulting attribution.
- Self-hosted Keycloak/PostgreSQL identity, verified-email registration, password
  reset, account/security console, optional TOTP, confirmed account deletion, and
  identity-bound profile/simulation data export.
- Separate no-network simulation worker with read-only filesystem and bounded
  CPU, memory, jobs, processes, and temporary storage.
- Dedicated TLS certificate and isolated immutable-release VPS delivery receiver.

The original CLI regressions are fixed: named-value edits now work, each sweep
has its own outputs, failed simulations return failure, new scaffolds contain
an analysis and do not overwrite existing files. The NAND example uses supported
ADC/DAC bridges; the RC example has sufficient default settling time.

## Verification boundary

Local verification for observation and AC on October 4: 237 Python tests,
20 frontend unit tests and 16 browser tests passed; combined backend/harness
coverage was 84.85%. Python lint/strict types, frontend
lint/production build, the production Python dependency audit, and the full npm
dependency audit passed. Python tests emit one upstream TestClient deprecation
warning; no tests were skipped, deleted, or weakened.

This is an early prototype, not the complete Phase 0/Phase 1 product in the
September design. Local and container checks use SHA-256-pinned ngspice 47;
CI builds the same engine. The analog editor and palette are live at revision
831f09c (verified earlier this session). The observation/sine/AC expansion is local
only and awaits an authorized push; its GitHub CI and public deployment have not run.
Real local containers verify the new AC worker operation along with all nine recipes,
analog transient output, proxy rejection and blocked outbound network. Identity
configuration was not changed by this feature; its deployment integration will run
again through the existing pipeline after a push.
Real identity integration covers native signup reachability, authorization
code/PKCE/nonce exchange, protected workbench access, forged-header rejection,
own-account export, and revocation at the next one-minute session refresh.
SMTP authentication is checked against the authorized active mail service.
Actual verification/reset email delivery must still be checked with a real inbox.
Browser tests cover recipe selection, actual simulation, value changes,
failed checks, export, responsive overflow, and automated accessibility.
The expanded browser suite uses two workers to match the service's two-job budget;
separate concurrency tests retain rejection of a third job across editor/recipe modes.
Automated accessibility checks are not a substitute for assistive-device testing.

All current models are generic/ideal. The editor has a bounded linear-analog graph,
not a full electronic parts/model library. There is no manufacturer model provenance,
rating validation, build-ready approval, or real hardware
verification. Arbitrary netlists remain prohibited.
Local mode remains unauthenticated and loopback-only. Hosted mode requires the
trusted identity gateway and attributes simulations to stable account IDs.
No AI-action route exists yet. Commercial launch still needs backup/recovery
drills, anti-abuse controls and quotas, audit retention, and reviewed legal pages.

## Next milestones

1. Extend the analog editor with nonlinear devices, manual routing/junction tools
   and undo, while preserving bounded structured input and synchronized playback.
2. Add the AI tool loop against bounded simulation actions, with explicit AI/user
   attribution and iterative spec checks; deepen per-recipe verification.
3. Add curated real component models with provenance and human verification.
4. Add persistent designs, backup/recovery verification, and per-account quotas.
5. Run the GitHub pipeline after an authorized push and check the live account
   creation/email flow on the actual Android client.

Use the live service and Git history to determine current deployment/push state;
these capabilities do not imply billing or commercial-release readiness.

See [the analog editor scope](plans/2026-10-03-analog-schematic-editor.md) for the
interaction, security boundaries and intentional first-slice limitations.
See [observation and AC](plans/2026-10-04-circuit-observation-and-ac.md) for the
approved design, implementation, limits and local verification evidence.
