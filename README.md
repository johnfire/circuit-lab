# circuit-lab

AI-assisted electronic circuit design for Raspberry Pi and other embedded
projects — analog **and** digital — powered by a headless **ngspice** engine
driven from a small Python harness.

> **Documentation:** [`HOW-TO.md`](HOW-TO.md) is the full guide, written for
> **both humans and AI agents** (the agent section covers the netlist
> conventions and verification steps to follow).

## Layout

```
circuit-lab/
  backend/               # local FastAPI catalog, bounded simulation workers, checks
  frontend/              # React/TypeScript workbench and browser regressions
  harness/
    run_circuit.py        # ngspice driver: netlist -> parsed results (op/data) + plots
  circuits/
    analog/               # R/C/L, dividers, MOSFET switches, LED, op-amp, level shifter
    digital/              # behavioral + (where used) XSPICE digital logic
  README.md
```

## Requirements

- Linux. ngspice 47 is a self-contained, no-sudo install under `~/.local`
  (built headless: `--with-x=no --enable-xspice`), so it needs no X11 and no
  root. `~/.local/bin` must be on `PATH`.
- Python 3 + optional `matplotlib` for `--plot`.

## Web prototype

The first workbench supports local and gated hosted modes: nine recipes, editable resistor/capacitor
values, real ngspice waveforms with zoom/cursor measurements, numerical checks,
a supported-component connectivity table, netlist inspection, and JSON export.
It does not yet have AI chat, schematic editing, or persistent saved designs.

The web prototype needs Python 3.12+, uv, and Node.js 26/npm, in addition to
ngspice. Locked Python and npm dependencies are committed.
From the repository root:

    uv sync --frozen --all-extras
    npm ci --prefix frontend
    npm run build --prefix frontend
    uv run uvicorn backend.application:app --host 127.0.0.1 --port 8010

Open http://127.0.0.1:8010 on this computer. This is not a public/mobile-hosted
deployment; do not bind it to the network or put an unauthenticated proxy in
front of it. Development mode: run the API above, then run the following
in another terminal:

    npm run dev --prefix frontend

All models are marked generic/ideal. Passing checks are not hardware approval,
component-rating verification, or permission to connect a Raspberry Pi.
The API accepts only registered recipes and bounded numeric overrides, not
arbitrary netlists. Each job has its own temporary directory and process group,
resource limits, timeouts, and a two-worker ceiling. Hosted mode uses the
network-isolated worker described in [the deployment runbook](deploy/README.md).

Run the same checks used by CI:

    uv run ruff check backend harness tests
    uv run mypy backend
    uv run pytest --cov=backend --cov=harness --cov-report=term-missing --cov-fail-under=70
    npm run lint --prefix frontend
    npm run build --prefix frontend
    cd frontend
    npx playwright install chromium
    npm run test:e2e

Simulation events are appended to /tmp/circuit-lab-audit.jsonl, with correlation
IDs and the local-user actor. Set CIRCUIT_AUDIT_PATH for a different local
destination. Missing audit storage rejects jobs without breaking the catalog.
Local mode has no accounts. Hosted mode requires a trusted gateway and records
its authenticated identity on simulation events. Hosted mode has a public signup
landing page and self-hosted Keycloak accounts; see [deployment runbook](deploy/README.md).
See [prototype status](docs/prototype-status.md) for scope and next milestones.

The MCP interface is being built separately. Its SDK and validated circuit,
measurement and schema foundations are implemented locally; remote access,
saved projects and AI editing are not enabled yet. See
[MCP implementation status](docs/mcp-implementation-status.md) for the exact
boundary and remaining work.

## Command-line quick start

```bash
# list example circuits
python3 harness/run_circuit.py list

# run a circuit and print its operating point / data tables
python3 harness/run_circuit.py run circuits/analog/voltage_divider.cir

# run with parameter substitutes
python3 harness/run_circuit.py run circuits/analog/rc_lowpass.cir --set R1=4700

# sweep a parameter (runs ngspice once per value)
python3 harness/run_circuit.py run circuits/analog/rc_lowpass.cir --sweep R1=4700,10000,22000

# render a plot of the first data CSV
python3 harness/run_circuit.py run circuits/analog/rc_lowpass.cir --plot /tmp/rc.png

# scaffold a new circuit
python3 harness/run_circuit.py new circuits/analog/my_circuit
```

## Netlist conventions (important for reliable parsing)

The harness reads results two ways:

1. **Operating-point / printed scalars** — any
   `v(node) = value` lines in the log (from `print v(x)` after `op`, `dc`,
   or `tran`) are reported as `v(node) = value`.
2. **Data tables** — every `*.csv` written by `wrdata` in the netlist's
   `.control` block. ngspice's `wrdata` is finicky: **pass ONE vector per
   call** (a single-vector `wrdata` yields a clean 2-column CSV
   `[abscissa, value]`). Passing several vectors to one call interleaves the
   abscissa and is unusable. So a typical `.control` block is:

```
.control
tran 0.01m 80m           # or: dc VIN 0 5 0.5   |  ac dec 10 1 1meg
wrdata v_in.csv v(in)     # one signal per file
wrdata v_out.csv v(out)
.endc
.end
```

`wrdata` writes relative to the ngspice working directory, which the harness
owns; your netlist should use plain relative filenames.

## Adding a circuit

1. Write a `.cir` netlist. Use the `.control` block for the analysis and one
   `wrdata` per signal you care about.
2. Reuse these building blocks:
   - **Analog**: R/C/L, V/I sources (DC `V in 0 5`, `PULSE(v1 v2 td tr tf pw per)`),
     diodes `D ... <model>`, MOSFETs `M <d g s b> <model>`, and a portable
     behavioral op-amp subcircuit (see `opamp_noninv.cir`).
   - **Digital**: behavioral logic via `B` sources, e.g. an inverter
     `B1 out 0 V = 3.3*(V(in)<1.65)`, a NAND
     `... V = 3.3*((V(a)<1.65)|(V(b)<1.65))`. XSPICE digital primitives
     (`a1 ...`) are also available when the exact gate model is wanted.

## Notes / pitfalls

- `op ; print v(x)` can return stale/zero values if the engine isn't fully
  initialised; prefer `dc`, `tran`, or `ac` plus `wrdata` for guaranteed data.
- The earlier "Arch package extracted to `~/.local`" shortcut is **not** used
  here: that binary hardcodes `/usr/lib/ngspice` code models and returns
  all-zero simulations when it can't find them. The harness uses the
  self-built headless ngspice 47 instead.
- Sweeps use the source **name** (`dc VIN 0 5 1`), not the node (`dc v(in)...`).
