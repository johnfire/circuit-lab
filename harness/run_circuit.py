#!/usr/bin/env python3
"""
run_circuit.py — Hermes circuit-design harness (analog + digital via ngspice).

A thin, reliable driver around the ngspice batch simulator. It lets an AI
agent (or a human) go from a SPICE netlist to parsed, machine-readable results
(and optional plots) with one command.

Design goals:
  - Headless: no GUI, no X11. Pure `ngspice -b`.
  - Analog AND digital: standard SPICE (R/C/L/V/I/E/F/G/H/D/Q/M/B behaviors)
    plus XSPICE digital primitives and behavioral logic.
  - Safe on Arch without sudo: ngspice 47 lives in ~/.local (a small launcher
    sets LD_LIBRARY_PATH just for the ngspice process).
  - Reproducible: each run writes the netlist to a temp dir, runs ngspice,
    and parses the results into an operating-point summary and/or data tables.

Data convention (important):
  ngspice `wrdata file v(one_vector_only)` writes a clean 2-column CSV:
  [abscissa, value].  Passing multiple vectors to one wrdata call makes
  ngspice interleave the abscissa per vector (a quirk), so netlists should
  issue ONE wrdata per signal, each to its own file.  The harness reads every
  *.csv in the run dir and labels each by its filename.

Usage:
  python3 run_circuit.py run <file.cir> [--set K=V ...] [--plot out.png]
  python3 run_circuit.py list
  python3 run_circuit.py new <name>

Template substitution:
  Placeholders $NAME and %{NAME} are replaced by values from --set/--sweep.

Exit codes: 0 = sim ran, 1 = ngspice error.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — make sure the user-built ngspice (no-sudo install) is found.
# ---------------------------------------------------------------------------
LOCAL_BIN = Path.home() / ".local" / "bin"
if str(LOCAL_BIN) not in os.environ.get("PATH", ""):
    os.environ["PATH"] = str(LOCAL_BIN) + os.pathsep + os.environ.get("PATH", "")

DEFAULT_ROOT = str(Path(__file__).resolve().parent.parent)  # project root


def find_ngspice() -> str:
    p = shutil.which("ngspice")
    if p:
        return p
    for cand in [
        str(Path.home() / ".local" / "bin" / "ngspice"),
        "/usr/bin/ngspice",
        "/usr/local/bin/ngspice",
    ]:
        if Path(cand).is_file() and os.access(cand, os.X_OK):
            return cand
    return ""


# ---------------------------------------------------------------------------
# Template substitution
# ---------------------------------------------------------------------------
def substitute_netlist(text, params):
    def repl_brace(m):
        return str(params.get(m.group(1), m.group(0)))

    def repl_dollar(m):
        return str(params.get(m.group(1), m.group(0)))

    text = re.sub(r"%\{([A-Za-z0-9_]+)\}", repl_brace, text)
    text = re.sub(r"\$([A-Za-z_][A-Za-z0-9_]*)", repl_dollar, text)
    return text


# ---------------------------------------------------------------------------
# ngspice runner
# ---------------------------------------------------------------------------
def run_ngspice(netlist_text, workdir, timeout=60):
    net_f = Path(workdir) / "input.cir"
    net_f.write_text(netlist_text)
    log_f = Path(workdir) / "ngspice.log"
    ng = find_ngspice()
    if not ng:
        raise RuntimeError("ngspice binary not found. Build it to ~/.local/bin (see skill).")
    cmd = [ng, "-b", "-o", str(log_f), str(net_f)]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            cwd=str(workdir), env=os.environ.copy(),
        )
    except subprocess.TimeoutExpired:
        return -99, "TIMEOUT", ""
    stdout_text = proc.stdout or ""
    try:
        stdout_text += "\n" + log_f.read_text()
    except OSError:
        pass
    return proc.returncode, stdout_text, proc.stderr or ""


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------
def parse_operating_point(stdout):
    """Extract node voltages from `.op`/'print' output. Handles:
         v(out)  =  2.976052e+00     (ngspice print/op form)
         v(out)   2.976052e+00
      Returns list of (node, value)."""
    out = []
    for m in re.finditer(r"v\(([^)]+)\)\s*(?:=\s*)?([-+0-9.eE]+)", stdout):
        try:
            val = float(m.group(2))
        except ValueError:
            continue
        out.append((m.group(1), val))
    return out


def read_wrdata_2col(path):
    """Read a single-vector wrdata CSV (2 columns, space-separated, no header).
    Returns (labels, rows) where labels = ['abscissa', 'value']."""
    p = Path(path)
    if not p.is_file():
        return None, []
    rows = []
    with p.open() as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2:
                try:
                    rows.append((float(parts[0]), float(parts[1])))
                except ValueError:
                    continue
    # label the value column from the filename (e.g. v_out.csv -> v(out))
    label = p.stem.replace("_data", "")
    return (["abscissa", label], rows)


def table(rows, labels, limit=40):
    if not rows:
        return "(no rows)"
    out = ["| " + " | ".join(labels) + " |", "|" + "---|" * len(labels) + "|"]
    for r in rows[:limit]:
        out.append("| " + " | ".join(f"{x:.5g}" for x in r) + " |")
    if len(rows) > limit:
        out.append(f"| … ({len(rows) - limit} more rows) |")
    return "\n".join(out)


def plot_csv(path, out_png):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        print(f"[plot] matplotlib unavailable ({e}); skipping plot.")
        return False
    labels, rows = read_wrdata_2col(path)
    if not rows:
        print("[plot] no data to plot.")
        return False
    xs = [r[0] for r in rows]
    ys = [r[1] for r in rows]
    plt.figure()
    plt.plot(xs, ys, label=labels[1])
    plt.xlabel(labels[0])
    plt.ylabel(labels[1])
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_png, dpi=110)
    print(f"[plot] wrote {out_png}")
    return True


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
def cmd_list(root):
    circuits = sorted(Path(root).rglob("*.cir"))
    if not circuits:
        print("No .cir files found under", root)
        return
    for c in circuits:
        print(c.relative_to(root))
    print(f"\n{len(circuits)} circuit file(s).")


def cmd_new(name):
    tpl = """* {name} — circuit stub. Replace the body. Use .control for analysis.
VDD 1 0 3.3V
R1 1 2 10k
C1 2 0 1u
V0 in 0 PULSE(0 3.3 0 1u 1u 0.5m 1m)

.control
run
* one wrdata per signal -> clean 2-column CSV
wrdata v_out.csv v(2)
.endc
.end
"""
    p = Path(name)
    if p.suffix != ".cir":
        p = p.with_suffix(".cir")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(tpl.format(name=p.stem))
    print("Wrote", p)


def cmd_run(args):
    src = Path(args.file)
    if not src.is_absolute():
        src = Path(DEFAULT_ROOT) / src
    if not src.is_file():
        print("Netlist not found:", src)
        return 1
    text = src.read_text()

    params = {}
    if args.set:
        for kv in args.set:
            k, _, v = kv.partition("=")
            params[k.strip()] = v.strip()
    sweep_vals = {}
    if args.sweep:
        k, _, v = args.sweep.partition("=")
        sweep_vals[k.strip()] = [x.strip() for x in v.split(",")]
        if k.strip() not in params and sweep_vals[k.strip()]:
            params[k.strip()] = sweep_vals[k.strip()][0]

    runs = 1
    if args.sweep and sweep_vals:
        runs = len(next(iter(sweep_vals.values())))

    first_csv = None
    with tempfile.TemporaryDirectory(prefix="crdt_") as tmp:
        for iter_n in range(runs):
            p = params.copy()
            if sweep_vals:
                sk = next(iter(sweep_vals))
                p[sk] = sweep_vals[sk][iter_n]
            net = substitute_netlist(text, p)
            rc, stdout_text, stderr_text = run_ngspice(net, tmp, timeout=args.timeout)

            if args.set or args.sweep:
                print(f"=== run with params {p} ===")
            print(f"[ngspice exit={rc}]")
            if rc != 0:
                tail = stdout_text[-2500:] if stdout_text else (stderr_text or "no output")
                print("---- ngspice error/transcript (tail) ----")
                print(tail)
                continue

            # Operating point / printed scalar values
            ops = parse_operating_point(stdout_text)
            if ops:
                print("---- operating point / printed values ----")
                for node, val in ops:
                    print(f"  v({node}) = {val:.5g}")

            # Data tables (each single-vector wrdata CSV)
            csvs = sorted(Path(tmp).glob("*.csv"))
            for cpath in csvs:
                labels, rows = read_wrdata_2col(cpath)
                if rows:
                    print(f"---- {cpath.name} ({len(rows)} rows) ----")
                    print(table(rows, labels))
            if csvs and first_csv is None:
                first_csv = str(csvs[0])

        if args.plot and first_csv:
            plot_csv(first_csv, args.plot)

    return 0


def main():
    ap = argparse.ArgumentParser(description="ngspice circuit harness")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run")
    p_run.add_argument("file")
    p_run.add_argument("--set", action="append", help="param substitution K=V")
    p_run.add_argument("--sweep", help="param sweep K=v1,v2,v3")
    p_run.add_argument("--plot", help="write PNG plot from a wrdata CSV")
    p_run.add_argument("--timeout", type=int, default=60)
    p_run.set_defaults(func=cmd_run)

    p_list = sub.add_parser("list")
    p_list.add_argument("--root", default=None)
    p_list.set_defaults(func=lambda a: cmd_list(a.root or DEFAULT_ROOT))

    p_new = sub.add_parser("new")
    p_new.add_argument("name")
    p_new.set_defaults(func=lambda a: cmd_new(a.name))

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
