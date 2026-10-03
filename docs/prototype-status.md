# Circuit Lab prototype — 2026-10-03

## Delivered locally

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
  This is not a schematic editor or a complete structured circuit model.
- Curated-only API, strict numeric limits, local origin/host restrictions, CSP,
  bounded worker processes, job timeouts, correlation IDs, and local audit records.
- Python unit/integration regressions, real-engine tests for every example,
  browser interaction/export tests, and desktop/mobile axe accessibility checks.
- Locked dependencies; main-branch CI and dependency scanning configuration.

The original CLI regressions are fixed: named-value edits now work, each sweep
has its own outputs, failed simulations return failure, new scaffolds contain
an analysis and do not overwrite existing files. The NAND example uses supported
ADC/DAC bridges; the RC example has sufficient default settling time.

## Verification boundary

Local verification on October 3: 56 Python tests and 2 browser tests passed;
combined backend/harness coverage was 76.55%. Python lint/strict types, frontend
lint/production build, the production Python dependency audit, and the full npm
dependency audit passed. Python tests emit one upstream TestClient deprecation
warning; no tests were skipped, deleted, or weakened.

This is a local prototype, not the complete Phase 0/Phase 1 deployment in the
September design. Live checks used ngspice 47 on this machine. CI uses the
Ubuntu ngspice package and must be confirmed after an authorized push.
Browser tests cover recipe selection, actual simulation, value changes,
failed checks, export, responsive overflow, and automated accessibility.
Automated accessibility checks are not a substitute for assistive-device testing.

All current models are generic/ideal. There is no manufacturer model provenance,
rating validation, full schematic graph, build-ready approval, or real hardware
verification. Processes have resource limits but are not yet dedicated
network-isolated containers; arbitrary netlists remain prohibited.
The API is unauthenticated and loopback-only. Audit actor user:local identifies
the local session, not a verified human identity; no AI-action route exists yet.
Do not expose the service publicly as-is.

## Next milestones

1. Add the structured circuit/netlist model and schematic editor.
2. Add the AI tool loop against bounded simulation actions, with explicit AI/user
   attribution and iterative spec checks; deepen per-recipe verification.
3. Add curated real component models with provenance and human verification.
4. Add persistent designs, authenticated access/account controls, and the separate
   no-network simulation-worker container.
5. Validate the container/CI path, deploy the approved hosted architecture, and
   check it on the actual Android client.

No remote deployment or push is included in this local prototype delivery.
