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

## Quick start

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
tran 0.01m 8m            # or: dc VIN 0 5 0.5   |  ac dec 10 1 1meg
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
