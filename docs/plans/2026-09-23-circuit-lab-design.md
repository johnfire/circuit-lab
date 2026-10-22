# circuit-lab — Product Design

- **Date:** 2026-09-23 · **Revised:** 2026-10-22
- **Status:** Agreed in brainstorming (Chris + Claude) on 2026-09-23. Revised 2026-10-22 to adopt the
  **MCP direction** that the 2026-10-03/04 build took (see §0). Live at
  `circuit-lab.christopherrehm.de`.
- **Current state of the build:** [`docs/prototype-status.md`](../prototype-status.md) and
  [`docs/mcp-implementation-status.md`](../mcp-implementation-status.md).

## 0. Revision 2026-10-22 — the MCP direction

The build diverged from the original plan in two ways. Chris reviewed both and accepted them:

1. **The AI lives outside the app and drives it through MCP.** We dropped the in-app chat agent with
   its own LLM provider (old D2/D5 and §4 "core loop"). Instead, any MCP-capable AI client (Claude
   Desktop/Code, Codex, …) connects to the authenticated `/mcp` endpoint and operates the software
   with the same structured, revisioned, undoable edits and real ngspice runs as the browser. **The
   user's AI client is the chat.**
2. **The schematic editor came first.** It's a second way to edit the same structured model (D3),
   so it was cheap to add early and the human and the AI share one circuit.

What this changes:

- **The verification loop is unchanged; who runs it changes.** The external AI edits the model,
  simulates, reads measurements and checks, and fixes before reporting. The MCP guide tells it never
  to claim a result it hasn't simulated.
- **The model is pluggable for free.** Whatever AI the user connects is the model. The model-router
  research uses the same benchmarks over MCP (§9 "Agent evals").
- **A trade-off we accept.** Users need an MCP-capable AI client. That suits the rusty EE (D1); for
  beginners, a later in-app chat can be built *as an MCP client of this same server*, not a second
  AI integration.
- **The parts library is now the next major piece.** Without it, MCP can only build ideal R/C/L
  circuits, and none of the benchmark circuits (§8) can be built.

## 1. What we're building

A **verification-first circuit design assistant**. You describe what you want to your AI client; it
operates Circuit Lab over MCP, proposes a circuit, **simulates and checks it before claiming it
works**, and you see the schematic, waveforms, a verification report, and a parts list. You can also
edit the same circuit directly in the browser.

The differentiator is verification, not "AI draws a circuit." A general chatbot will hand you a circuit
that fries your Pi; this tool must never present an unverified design as working.

**Scope limit (safety):** low-voltage DC only (≤ 24 V) until further notice. No mains.

## 2. Who it's for

- **Primary v1 user: the rusty EE** — knows the theory, has lost the specifics (which MOSFET is
  logic-level at 3.3 V, current best practice, exact formulas). Chris is this user, so the tool is
  dogfooded from day one.
- **Hobbyists/makers** are served by the same product via an **explain-level dial** (turned up, with
  Flashkarte lesson links), not a separate mode.
- **Working EEs** are served with the dial turned down (terse output, raw netlists). Pro-only
  features (tolerance analysis, vendor models, PCB export) come later.
- **Flashkarte** complements the tool rather than gating it: lessons are linked in context when a
  concept comes up, and the course is recommended (not required) for beginners.

## 3. Decisions

| # | Decision | Why |
|---|---|---|
| D1 | Primary user = rusty EE; one explain-level dial for everyone | Bridges hobbyist and pro; dogfoodable; one product, not three |
| D2 | ~~Chat-first in phase 1; schematic-first later~~ **Revised:** AI chat happens in the user's own MCP client; the browser schematic editor shipped first | See §0 |
| D3 | The circuit lives in one **structured model**; MCP edits, netlist, and schematic all derive from it | The browser editor and the AI edit the same revisioned circuit |
| D4 | Hosted on goserver, single-user at first, via CI/CD | Matches the CI-is-the-gate workflow; forces the sandbox early; multi-user deferred |
| D5 | ~~Pluggable LLM provider interface, starting on Claude~~ **Revised:** no LLM inside the app; any MCP client can drive it | Pluggability for free; no API cost in the app; see §0 |
| D6 | Curated parts library; generic parts only as a clearly labelled fallback | "Verified" is only as good as the models behind it |
| D7 | Only a human can mark a part `verified` | Tests prove model ≡ part file; only a human reading the datasheet catches a misread datasheet |
| D9 | Parts are `part.json` with **structured model parameters**, not YAML + free-text `model.lib` | No new dependency; the browser imports it directly; our code generates every `.model` line, so no file-supplied SPICE text ever reaches ngspice |
| D8 | Backend Python (FastAPI); frontend React + TypeScript | Harness is already Python; React has the best diagram/canvas ecosystem |

## 4. Architecture

### Core loop (revised 2026-10-22: the AI is an external MCP client)

1. The user describes the goal to their own AI client and shares a circuit (project or live
   workspace) with it from the browser. The grant is bounded, it expires, and it can be revoked.
2. The AI never writes SPICE. It calls MCP tools that edit the structured model:
   `apply_circuit_edits` (`put_part`, `connect`, `disconnect`, `set_timing`, `set_sweep`, …),
   `validate_circuit`, `list_components` / `list_library_parts`.
3. Our code validates the model, generates the netlist, runs it in the simulation worker
   (`simulate_circuit`), and evaluates checks (`measure_signals`, `evaluate_checks`, part ratings).
4. The AI fixes and re-simulates **before** reporting. Every edit is a revision with undo; the human
   sees the same circuit change on the grid.
5. The user gets the design plus its evidence, or an honest "couldn't make this work, here's why."

### Two kinds of checks

- **Automatic part-limit checks**: every part's max voltage, current, and power dissipation from the
  library, checked on every simulation. The agent cannot forget them.
- **Intent checks**: written by the agent from the user's requirements (e.g. "output settles within
  50 ms", "GPIO current ≤ 8 mA"), shown in plain language so the user can confirm it understood.

### Components (each its own container)

| Component | Role |
|---|---|
| Frontend | React + TS: schematic editor, observation/scope, AC plots, sharing |
| API | FastAPI: REST for the browser + authenticated `/mcp` for AI clients, sharing one service layer |
| Identity | Self-hosted Keycloak (separate store): accounts, OAuth for MCP clients |
| Simulation worker | ngspice in a locked-down container: no network, CPU and time limits, read-only FS |
| Database | Postgres (application-only): projects, immutable revisions, runs, audit log |
| Parts library | `circuits/parts/<category>/<id>/part.json` in the repo, loaded at startup |

### Security

- Netlists are **generated by our code from the model**, so neither the AI nor a user can inject
  ngspice `.control` commands such as `shell`.
- The simulation sandbox is the second layer (defence in depth), and is required anyway before any
  raw-netlist mode for pro users.

### Failure isolation

- ngspice hang or crash → only that job fails; the agent sees the error.
- AI client disconnected or MCP disabled → the browser editor and simulation keep working.

## 5. Parts library

One part = one file, `circuits/parts/<category>/<id>/part.json` (D9), containing:

- **Identity**: name, kind (diode, LED, Zener, NMOS/PMOS, NPN/PNP), package, description, and the
  datasheet URL.
- **Model**: a model type (`D`, `NPN`, `PNP`, `VDMOS`) plus **named numeric parameters**. Our code
  writes the `.model` line, so the file holds no SPICE text.
- **Ratings**: absolute maximums (e.g. `vds_max`, `id_max`, `pd_max`), each with a unit and a
  `source` saying where the number came from.
- **Characterization tests, as data**: e.g. `{"test": "mosfet_rds_on", "vgs": 4.5, "id": 0.075,
  "max": 5.3}`. A generic runner turns each into a small real-ngspice simulation. Adding a part never
  requires writing Python.
- **Trust**: `draft` or `verified`. A part can only be marked `verified` when it has a datasheet
  URL, every rating cites a datasheet page, and a named human reviewer and date are recorded. The
  loader enforces this (D7).

**Adding a part:**

1. `python -m backend.parts_cli new mosfet/irlz44n` scaffolds the file.
2. Fill it in by hand, or have an AI draft it from the datasheet with page citations.
3. `python -m backend.parts_cli verify irlz44n` runs its characterization tests against real ngspice.
4. A human checks the cited values against the datasheet and records the review → `verified`.

**In circuits:** library parts are placed like any other part. Every transient run automatically
checks each library part against its ratings (peak voltage, current, power) and reports pass/fail.
The result always states each part's trust level: draft parts are usable, but never reported as
datasheet-verified.

**Fallback:** when no suitable part exists, the AI uses ideal parts, says so, and lists the specs a
real part must meet.

## 6. User interface

- **The chat is the user's AI client** (MCP). The browser is the shared workspace that the human and
  the AI both edit.
- **Browser workspace** (built), all derived from the model:
  1. **Schematic editor**: place, wire, move, rotate; standard or custom values.
  2. **Observation**: live node voltages and current arrows on the grid, probes, scope, playback.
  3. **AC analysis**: gain/phase plots, frequency cursor, phasors.
  4. **Projects and sharing**: save, revisions, undo, share with an AI client, revoke.
- **Still to come:** a library parts shelf with trust badges, a ratings/verification panel per run,
  a BOM view, and the explain-level dial with Flashkarte links.

## 7. Roadmap (status as of 2026-10-22)

### Phase 0 — Skeleton, live — **done**

- CI (lint, types, tests, dependency audit) deploying to goserver at
  `circuit-lab.christopherrehm.de`; the 9 example circuits are regression tests.

### Phase 1 — Core loop (MVP) — **in progress**

- ✅ Circuit model, netlist generator, sandboxed simulation worker (transient and AC).
- ✅ Schematic editor and observation UI (built ahead of the original plan).
- ✅ MCP server with revisioned edits, runs, measurements, and undo. Deployed but **switched off**
  pending encrypted off-host backups and a real AI-client sign-in test (see
  `docs/mcp-implementation-status.md`).
- ✅ **Parts library** (2026-10-22): `part.json` format, loader with trust gating,
  characterization runner and `parts_cli`, 23 draft starter parts (diodes, Schottkys, Zeners,
  LEDs, BJTs, N/P MOSFETs). Devices work in the circuit model, the browser editor, transient/AC
  analysis and MCP (`list_library_parts`, `get_library_part`). Every transient run checks ratings
  with ngspice `meas` on raw solver points, so it catches spikes between output frames. Transient
  analysis uses Gear integration to stop the trapezoidal ringing that inductive switching caused.
- ✅ **Op-amps, regulators and boards** (2026-10-22): op-amps (LM358, LM324, TL072, MCP6002) and
  linear regulators (7805, 7812, LM1117-3.3, LM317, MCP1700-3.3) as behavioral subcircuits
  generated from datasheet-style numbers; development boards (Pi 4, Pi 5, Pico, Uno R3,
  ESP32-DevKitC) with header pinouts, a "Board pin" part with pin protection checks, a pinout
  view, and MCP `list_boards` / `get_board`. Switching regulators and firmware simulation are
  out of scope for now.
- ✅ **Circuit library** (2026-10-22): 10 curated blocks with CI-checked expectations; insert/open in
  the browser; MCP `list_circuit_blocks`, `get_circuit_block`, `insert_block`. Personal saved circuits
  use the existing project storage, which goes live with the backup gate.
- ✅ Daily backups (on the VPS for now; off-host copy still to do) and saved projects + MCP switched
  on in production (2026-10-22).
- ⬜ KiCad export (netlist + BOM with footprints and LCSC numbers) as the path to ordering PCBs.
- ⬜ Human review of draft parts and boards against datasheets → `verified`.
- ⬜ Benchmark 1 (GPIO → MOSFET → relay) simulates correctly in tests; it still needs an AI
  client over MCP to design it end to end once MCP is switched on. Benchmark 2's op-amp option
  needs subcircuit support; its divider + Zener option works today.
- **Done when:** all three benchmark circuits (§8) are designed end to end on the live site **by an
  AI client over MCP**, and verified.

### Phase 2 — Make it good

- Grow the library beyond the current 32 parts; vendor macromodels where the behavioral ones fall short.
- Datasheet-PDF → draft-part flow; BOM view; explain-level dial with Flashkarte links.

### Phase 3 — Beyond the schematic

- Breadboard/wiring view; better auto-layout for AI-created circuits.

### Phase 4 — Open to others

- Public accounts already exist (Keycloak); still needed: GDPR review, rate limits and quotas at
  scale, anti-abuse, legal pages, and possibly an in-app chat built as an MCP client.

### Later (pro EE)

- Tolerance / Monte-Carlo analysis, vendor SPICE models, KiCad export.

The Flashkarte course can be written in parallel at any time; it blocks nothing.

## 8. Benchmark circuits (phase 1 acceptance)

1. **Drive a 12 V relay or solenoid from a 3.3 V GPIO**: logic-level MOSFET, flyback diode, gate
   resistor, pull-down.
2. **Read a 0–5 V sensor into a 3.3 V ADC**: divider or op-amp buffer, with over-voltage
   protection.
3. **PWM → smooth analog voltage**: RC filter sized for a ripple target.

Replace these with real projects Chris wants to build when they come up.

## 9. Testing

| Tier | What | When |
|---|---|---|
| Unit | Model validation, netlist generation, result parsing, check evaluation | Every push |
| Integration | Real ngspice in the sandbox: the 9 example circuits and every part's characterization tests | Every push |
| End-to-end | Playwright through the browser editor; scripted MCP client sessions against a disposable stack | Every push |
| Agent evals | A real AI client over MCP on the benchmark circuits, scored on convergence, checks passed, retries, and cost | On demand / nightly |

Agent evals are also the data source for the model-router research: the same benchmarks run
against different models.

## 10. Error handling

1. **Agent can't converge** after N attempts → it stops and says what failed and why. Never presents
   an unverified design as working.
2. **Simulation timeout or crash** → that job fails; the agent sees the error and can adjust.
3. **Invalid model edit** → rejected by the model validator with a clear error, before simulation.
4. **AI client unavailable** → designs stay viewable, editable, and re-simulatable in the browser.
5. **Every AI action is logged with a correlation ID**, so any design's history can be traced.

## 11. Known unknowns

- **Competitor landscape** (Tinkercad Circuits, Falstad, CircuitLab, Flux.ai) is from model training
  data, not a current check. Verify before positioning publicly.
- **Schematic auto-layout quality**: expect plain output in phase 1; the renderer choice is still
  open.
- **Sequential digital logic** (latches, flip-flops) does not settle in the current ngspice/XSPICE
  setup (see `HOW-TO.md`). Out of scope until solved.
- **LLM cost per design session**: now paid by the user's own AI client, not the app; still worth
  measuring in agent evals.
- **Draft model accuracy**: starter-part model parameters and ratings were drafted without a datasheet
  check. Characterization tests prove each model meets its *stated* specs, not that the specs are
  right. Human review against the datasheet (D7) is what closes that gap.
