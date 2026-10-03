# Analog schematic editor — accepted first slice

Chris chose schematic symbols and analog-first simulation on October 3, 2026.
This reprioritizes the schematic editor ahead of the AI design loop. Existing
curated examples, login, theme and landing analytics remain available.

## Interaction

- Open **Build circuit** in the workbench. Begin with an editable pulse-driven RC
  example, or confirm replacement with a blank grid.
- Select R, C, L, DC source, pulse source or ground. Place with a grid click or
  explicit column/row controls. Drag, move with arrows, or rotate by 90 degrees.
- Choose a standard value or enter a bounded numeric value in SI units. Configure
  pulse period, high duration and initial delay separately.
- Connect two terminal buttons or use the terminal selector. Wire endpoints are
  stable part/terminal references, not coordinates. Moving/rotation preserves
  electrical connections. Crossings/proximity never create implicit junctions.
- Run a transient analysis. Scrub, step, play/pause, loop, change viewing rate or
  select a playback interval. Changing electrical values/wiring/timing clears old
  readings. Layout-only edits preserve results.
- Export/import a compact structured circuit file, export a simulation report,
  or export the current browser session's edit history. Browser drafts are scoped
  by a noncredential digest of the authenticated actor; no account synchronization.

## Solver and trust boundaries

The browser submits only a structured graph and timing parameters. The API checks
the graph before recording an audited job; the isolated worker checks the schema
again. Generated node/component names and all executable SPICE syntax originate
on the server. No raw netlists, model text, expressions, includes or shell actions
are accepted. Existing host/origin/proxy controls and request limits still apply.

Limits: 20 parts, 40 wires, 8 KiB HTTP/IPC request, 10–2000 output intervals,
10 seconds simulated duration, at most 1000 pulse periods, two concurrent jobs,
existing subprocess deadlines/resources, and 4 MB IPC output. Missing terminals,
duplicate identifiers/wires, self-links, shorts across a component and floating
islands are rejected. Solver convergence is not guaranteed for all allowed graphs;
one failed job must not break catalog access or subsequent jobs.

Each active part gets a generated zero-volt series current probe. Positive branch
current is terminal 0 to terminal 1; a supplying voltage source usually reads
negative. Ground symbols share node 0. All node voltages and branch currents are
exported together on a single time axis, uniformly interpolated with ngspice
`linearize`. Report validation checks trace lengths, finite values, uniform time,
correlation ID, circuit identity and expected frame count/interval.

Solver output interval/maximum internal step is distinct from playback rate.
The UI explicitly labels rate as simulated milliseconds per real second. Fast
events still require an appropriately small solver/output interval; slow playback
does not increase simulation accuracy.

## Verification and limits

Unit tests cover graph/parameter/parser rejection and playback math. Integration
tests use the actual ngspice engine for RC charging, a DC divider, and inductance;
API and Unix-socket tests cover audit failure, no fallback and malformed jobs.
Browser tests cover blank-grid construction, standard values, terminal wiring,
movement/rotation, simulation, synchronized readings, slow playback, import refusal,
export, reload persistence and desktop/mobile automated accessibility. CI's hosted
container checks now include a real custom analog graph and injection rejection.

This is an ideal linear-analog prototype. No diode/transistor/op-amp models,
manufacturer provenance, tolerances, component ratings, Pi GPIO protection checks,
AI loop, cloud design storage, undo stack or manual wire routing are included.
Initial state is ngspice's DC operating point; the pulse example starts low so its
capacitor begins discharged. Every disconnected terminal must be explicitly wired;
crossing-only junctions and an isolated ground symbol do not count.

Shared/commercial browser use still needs a reviewed local-data lifecycle, including
clearing browser drafts during account deletion; the current identity service deletes
server-owned data, not locally exported files or browser storage. Browser edit history
is a session-only convenience, not a durable compliance audit. Server simulation audit
records remain identity-bound and fail closed when storage is unavailable.

Delivery: commit on main; hold push until Chris authorizes it. Production changes
must pass the existing GitHub checks and CI/CD receiver, not an out-of-band deploy.
