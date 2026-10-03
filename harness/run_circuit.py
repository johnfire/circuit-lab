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
import math
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
def substitute_netlist(text: str, params: dict[str, str]) -> str:
    """Apply numeric placeholders or explicit passive-component overrides."""
    for name, value in params.items():
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name):
            raise ValueError(f"Invalid parameter name: {name}")
        if not re.fullmatch(r"[+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?(?:meg|[TGMKkmunpf])?", value):
            raise ValueError(f"Invalid numeric value for {name}")
        placeholder = re.compile(r"%\{" + re.escape(name) + r"\}|\$" + re.escape(name) + r"\b")
        if placeholder.search(text):
            text = placeholder.sub(lambda _: value, text)
            continue
        component = re.compile(
            r"^(" + re.escape(name) + r"\s+\S+\s+\S+\s+)\S+",
            re.MULTILINE | re.IGNORECASE,
        )
        if name[0].upper() not in "RCL" or not component.search(text):
            raise ValueError(f"Unknown editable parameter: {name}")
        text = component.sub(lambda match: match.group(1) + value, text)
    return text


# ---------------------------------------------------------------------------
# ngspice runner
# ---------------------------------------------------------------------------
def run_ngspice(netlist_text: str, workdir: str | Path, timeout: int = 60) -> tuple[int, str, str]:
    """Execute ngspice with a deadline and return its exit status and transcripts."""
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
def parse_operating_point(stdout: str) -> list[tuple[str, float]]:
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


def read_wrdata_2col(path: str | Path) -> tuple[list[str], list[tuple[float, float]]]:
    """Read a single-vector wrdata CSV (2 columns, space-separated, no header).
    Returns (labels, rows) where labels = ['abscissa', 'value']."""
    p = Path(path)
    if not p.is_file():
        return [], []
    rows = []
    with p.open() as f:
        for line in f:
            parts = line.split()
            if len(parts) == 2:
                try:
                    row = (float(parts[0]), float(parts[1]))
                    if all(math.isfinite(value) for value in row):
                        rows.append(row)
                except ValueError:
                    continue
    # label the value column from the filename (e.g. v_out.csv -> v(out))
    label = p.stem.replace("_data", "")
    return (["abscissa", label], rows)


def table(rows: list[tuple[float, float]], labels: list[str], limit: int = 40) -> str:
    """Format bounded simulation samples as a Markdown table."""
    if not rows:
        return "(no rows)"
    out = ["| " + " | ".join(labels) + " |", "|" + "---|" * len(labels) + "|"]
    for r in rows[:limit]:
        out.append("| " + " | ".join(f"{x:.5g}" for x in r) + " |")
    if len(rows) > limit:
        out.append(f"| … ({len(rows) - limit} more rows) |")
    return "\n".join(out)


def plot_csv(path: str, out_png: str) -> bool:
    """Render optional matplotlib output and report whether a file was produced."""
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
def cmd_list(root: str) -> None:
    """List available circuit recipes."""
    circuits = sorted(Path(root).rglob("*.cir"))
    if not circuits:
        print("No .cir files found under", root)
        return
    for c in circuits:
        print(c.relative_to(root))
    print(f"\n{len(circuits)} circuit file(s).")


def cmd_new(name: str) -> None:
    """Create a runnable circuit without overwriting an existing file."""
    tpl = """* {name} — circuit stub. Replace the body. Use .control for analysis.
R1 in 2 10k
C1 2 0 1u
V0 in 0 PULSE(0 3.3 0 1u 1u 0.5m 1m)

.control
tran 10u 80m
* one wrdata per signal -> clean 2-column CSV
wrdata v_out.csv v(2)
.endc
.end
"""
    p = Path(name)
    if p.suffix != ".cir":
        p = p.with_suffix(".cir")
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("x") as circuit_file:
        circuit_file.write(tpl.format(name=p.stem))
    print("Wrote", p)


def parse_run_parameters(args: argparse.Namespace) -> list[dict[str, str]]:
    """Expand validated CLI options into independent parameter sets."""
    parameters = {}
    for assignment in args.set or []:
        name, separator, value = assignment.partition("=")
        if not separator or not name or not value:
            raise ValueError("Use --set NAME=VALUE")
        parameters[name.strip()] = value.strip()
    if not args.sweep:
        return [parameters]
    name, separator, values = args.sweep.partition("=")
    if not separator or not name or not values:
        raise ValueError("Use --sweep NAME=VALUE,VALUE")
    if any(not value.strip() for value in values.split(",")):
        raise ValueError("Sweep values must not be empty")
    return [{**parameters, name.strip(): value.strip()} for value in values.split(",")]


def print_simulation_tables(workdir: str, transcript: str) -> list[Path]:
    """Render only the current run's operating point and CSV files."""
    for node, voltage in parse_operating_point(transcript):
        print(f"  v({node}) = {voltage:.5g}")
    csv_paths = sorted(Path(workdir).glob("*.csv"))
    for csv_path in csv_paths:
        labels, rows = read_wrdata_2col(csv_path)
        if not rows or len(csv_path.read_text().splitlines()) != len(rows):
            raise ValueError(f"Malformed or empty simulator output: {csv_path.name}")
        print(f"---- {csv_path.name} ({len(rows)} rows) ----")
        print(table(rows, labels))
    return csv_paths


def simulation_error(status: int, transcript: str, stderr: str) -> str | None:
    """Treat both failed exits and reported analysis/model errors as failures."""
    if status == -99:
        return "Simulation timed out"
    if status != 0 or re.search(r"(?im)^error\b|simulation interrupted", transcript):
        return "ngspice rejected the circuit"
    if re.search(r"(?i)unrecognized parameter|timestep too small|failed", transcript + stderr):
        return "ngspice reported an invalid model or failed analysis"
    return None


def run_cli_job(netlist: str, values: dict[str, str], args: argparse.Namespace,
                render_plot: bool) -> bool:
    """Execute, validate, and display one independent simulation job."""
    with tempfile.TemporaryDirectory(prefix="crdt_") as workdir:
        try:
            status, transcript, stderr = run_ngspice(netlist, workdir, timeout=args.timeout)
        except (RuntimeError, OSError) as error:
            print(str(error))
            return False
        print(f"=== run with params {values} ===")
        print(f"[ngspice exit={status}]")
        error_detail = simulation_error(status, transcript, stderr)
        if error_detail:
            print(error_detail)
            print((transcript or stderr)[-2500:])
            return False
        try:
            csv_paths = print_simulation_tables(workdir, transcript)
        except ValueError as error:
            print(str(error))
            return False
        if not csv_paths:
            print("Simulation produced no waveforms")
            return False
        return not render_plot or plot_csv(str(csv_paths[0]), args.plot)


def cmd_run(args: argparse.Namespace) -> int:
    """Run isolated sweep jobs and propagate any failure to the CLI."""
    src = Path(args.file)
    if not src.is_absolute():
        src = Path(DEFAULT_ROOT) / src
    if not src.is_file():
        print("Netlist not found:", src)
        return 1
    try:
        parameter_sets = parse_run_parameters(args)
        netlists = [substitute_netlist(src.read_text(), values) for values in parameter_sets]
    except ValueError as error:
        print(str(error))
        return 1
    outcomes = [run_cli_job(netlist, parameter_sets[index], args, bool(args.plot and index == 0))
                for index, netlist in enumerate(netlists)]
    return int(not all(outcomes))


def main() -> int:
    """Dispatch the circuit harness command line."""
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
    exit_status = args.func(args)
    return exit_status if isinstance(exit_status, int) else 0


if __name__ == "__main__":
    sys.exit(main())
