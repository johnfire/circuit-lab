# circuit-lab — How to Use

A small toolkit for designing and **verifying** electronic circuits — especially
things you'd add to a Raspberry Pi or other embedded project — using the
**ngspice** simulator driven from a Python harness. Headless, no root, works
for both analog and digital.

This document is written for two audiences. **Read the part that fits you.**
Humans: sections under "For Humans". AI agents: sections under "For Agents".

---

# For Humans

## 1. What this is

- `harness/run_circuit.py` — turns a SPICE netlist (`.cir`) into parsed,
  machine-readable results: an operating-point summary plus data tables
  (optional PNG plot).
- `circuits/analog/` and `circuits/digital/` — ready-to-run example circuits.
- The engine is **ngspice**, the industry-standard Berkeley SPICE descendant.

The point: you describe a circuit in SPICE, we run it, and you get numbers
(voltages, currents, waveforms) instead of guessing.

## 2. Requirements

- Linux.
- `ngspice` on your `PATH`. Install however you like:
  - Arch: `sudo pacman -S ngspice`
  - Debian/Ubuntu: `sudo apt install ngspice`
  - No sudo (user build): see the README / `docs` for the source build.
- Python 3. Optional `matplotlib` for `--plot`.

Verify it's there:

```bash
ngspice -v        # should print "ngspice-47" or similar
```

## 3. Quick start

```bash
cd circuit-lab

# list the example circuits
python3 harness/run_circuit.py list

# run one and see results
python3 harness/run_circuit.py run circuits/analog/voltage_divider.cir

# a transient circuit (RC low-pass, PWM->analog DAC)
python3 harness/run_circuit.py run circuits/analog/rc_lowpass.cir

# substitute a parameter
python3 harness/run_circuit.py run circuits/analog/rc_lowpass.cir --set R1=4700

# sweep a parameter (runs ngspice once per value)
python3 harness/run_circuit.py run circuits/analog/rc_lowpass.cir --sweep R1=4700,10000,22000

# write a plot of the first data table
python3 harness/run_circuit.py run circuits/analog/rc_lowpass.cir --plot /tmp/rc.png

# scaffold a new circuit
python3 harness/run_circuit.py new circuits/analog/my_circuit
```

## 4. Reading the results

The harness prints:

1. `[ngspice exit=N]` — 0 = the simulation ran.
2. A list of printed operating-point / scalar values (`v(node) = value`).
3. One table per data file the netlist wrote (`wrdata`). The first column is
   the abscissa (time for `tran`, input for `dc`, frequency for `ac`); the
   second is the signal value.

If `exit != 0`, the tail shows the ngspice error — usually a netlist typo.

## 5. Writing your own circuit

A SPICE netlist describes components between named nodes. A minimal one:

```spice
* comment
VIN in 0 5V                  ; 5V source, in -> ground
R1 in out 10k                ; 10k resistor, in -> out
R2 out 0 6.8k                ; 6.8k resistor, out -> ground

.control
dc VIN 0 5 0.5               ; sweep VIN from 0..5 in 0.5V steps
wrdata v_out.csv v(out)      ; write the output to a CSV
.endc
.end
```

Run it:

```bash
python3 harness/run_circuit.py run circuits/my_circuit.cir
```

### The `.control` block (important)

Everything in `.control` ... `.endc` drives the analysis. Common commands:

| Command | What it does |
|---|---|
| `dc SOURCE start stop step` | DC sweep (SOURCE is the *source name*, e.g. `VIN`) |
| `tran tstep tstop` | Time-domain (transient) |
| `ac dec points fstart fstop` | Frequency response |
| `op` | DC operating point |
| `wrdata file v(node)` | Write a 2-column CSV `[x, value]` |

**One `wrdata` per signal.** ngspice's `wrdata` interleaves the abscissa if you
pass several vectors to one call, making the result unusable. Write one vector
per file.

### Building blocks to reuse

- Voltage sources: `V in 0 5` (DC), `V in 0 PULSE(0 3.3 0 1u 1u 0.5m 1m)` (square).
- Resistors `R`, capacitors `C`, inductors `L`.
- Diodes `D ... <model>`, MOSFETs `M <d g s b> <model>`.
- Ideal op-amp macro (see `opamp_noninv.cir`).
- Logic via `B` sources (single comparison), or XSPICE digital primitives.

## 6. Example walkthrough: an RC low-pass (PWM -> analog DAC)

A Raspberry Pi PWM pin outputs a 3.3V square wave. Filter it with an RC
low-pass and you get a steady analog level.

```spice
VIN in 0 PULSE(0 3.3 0 1u 1u 0.5m 1m)   ; 1 kHz PWM, 0..3.3V
R1 in out 10k
C1 out 0 1u                             ; tau = 10ms

.control
tran 0.01m 8m
wrdata v_in.csv v(in)
wrdata v_out.csv v(out)
.endc
.end
```

The output `v(out)` settles near the PWM average and the ripple is small — that
*smooths* the PWM into an analog voltage you can read.

---

# For Agents

## 1. When to use this

Load the **`circuit-design`** Hermes skill when the task is: designing,
simulating, or verifying an electronic circuit; writing a SPICE netlist; or
"build an adapter / filter / switch / level shifter for a Raspberry Pi."
It lives in `skills/software-development/circuit-design/`.

The project root is `~/circuit-lab/`.

## 2. Environment

- `ngspice` must be on `PATH` (find it via `shutil.which`). On this machine it
  is a self-built headless ngspice 47 at `~/.local/bin/ngspice` (see the
  `circuit-design` skill for the no-sudo build). `~/.local/bin` is already on
  `PATH`.
- The harness adds `~/.local/bin` to `PATH` itself as a fallback.
- The harness writes everything to a temp dir per run; netlists should give
  `wrdata` relative filenames.

## 3. Netlist conventions (CRITICAL — read before writing a netlist)

These are the gotchas that break results or lose time:

1. **`wrdata` = ONE vector per call.** `wrdata file v(out)` → clean 2-column
   `[x, value]` CSV. `wrdata file time v(in) v(out)` → ngspice interleaves the
   abscissa per vector and the output is unusable. One signal, one `wrdata`.
2. **DC sweeps use the source NAME, not the node.** `dc VIN 0 5 1`, never
   `dc v(in) 0 5 1`.
3. **`op ; print v(x)` can be stale/zero.** Prefer `tran`, `dc`, or `ac` plus
   `wrdata`. The harness also parses `v(x) = value` lines from the log.
4. **Multi-input logic — use XSPICE digital primitives.** Behavioral `B` sources
   converge for a *single* comparator (an inverter works) but multi-input logic
   (`V = ... (a>1.65)*(b>1.65)`) fails with *"timestep too small"*. Use the
   XSPICE **`d_nand`** code model instead — event-driven, no convergence issues.
   Verified recipe (output reads as logic **0/1**, not rail voltage):

   ```spice
   vdummy dummy 0 DC=0              ; required — stabilises the digital OP
   a_x [a b] out nand1              ; inputs in brackets, output scalar
   .model nand1 d_nand (rise_delay=1n fall_delay=1n in_low=0.7 in_high=1.6 out_low=0 out_high=3.3)
   ```

   **Sequential memory (SR latch / FF) does NOT settle in this ngspice build** —
   cross-coupled digital feedback starts in the X (unknown) state and the
   outputs sit at 0.5 (`1.65V` = threshold). Verified: `d_srlatch` (any pin/bind
   order) and two cross-coupled `d_nand`s both give 0.5. Sequential logic here
   needs a proper init path that ngspice's event-driven XSPICE doesn't provide
   cleanly; treat `circuits/digital/inverter_behavioral.cir`,
   `nand_xspice.cir`, and `debounce_rc.cir` as the verified digital set.
5. **`B`-source logic operators.** ngspice `B` sources accept arithmetic
   (`+ - * /`) and comparisons (`< > == !=`) but NOT `&`, `|`, `~`, or `if()`.
   Build logic from arithmetic on 0/1 comparisons, or use XSPICE.
6. **op-amp clamps**: use `MIN(MAX(expr, lo), hi)`, not `LIMIT`.

## 4. Operating the harness

```bash
python3 ~/circuit-lab/harness/run_circuit.py list
python3 ~/circuit-lab/harness/run_circuit.py run circuits/analog/rc_lowpass.cir
python3 ~/circuit-lab/harness/run_circuit.py run circuits/analog/rc_lowpass.cir --set R1=4700
python3 ~/circuit-lab/harness/run_circuit.py run circuits/analog/rc_lowpass.cir --sweep R1=4700,10000,22000
python3 ~/circuit-lab/harness/run_circuit.py run circuits/analog/rc_lowpass.cir --plot /tmp/rc.png
python3 ~/circuit-lab/harness/run_circuit.py new circuits/analog/my_circuit
```

Paths are relative to `~/circuit-lab/`. `--set K=V` substitutes `$K` / `%{K}`
placeholders; `--sweep K=v1,v2,v3` runs once per value.

## 5. How to verify a design (do this every time)

Treat simulation as a check, not a prediction. Verify against real ngspice
output before reporting a design as working:

1. Confirm `[ngspice exit=0]`.
2. Sanity-check the numbers against theory:
   - Divider: expect `VOUT = VIN * R2/(R1+R2)`.
   - Op-amp gain: `1 + Rf/Rg`.
   - RC low-pass: ripple small if `R*C >> period`.
3. For switching circuits, confirm the output actually transitions (HIGH↔LOW,
   12V↔~0V) over the sweep.
4. If a circuit "runs" but the values are implausible, check the netlist and the
   analysis (e.g. is the source node named right?).

## 6. Pitfalls recap

- Arch **binary package** extracted to `~/.local` gives **all-zero** results
  (it hardcodes `/usr/lib/ngspice`). Use the self-built headless ngspice.
- The `circuit-design` skill is authoritative on the working setup.
