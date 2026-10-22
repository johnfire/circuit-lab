"""Command line for the parts library: list, verify against ngspice, scaffold new parts."""

import argparse
import json
import sys
from pathlib import Path

from backend.part_characterization import CharacterizationResult, characterize
from backend.part_library import INDEX_PATH, LIBRARY, PARTS_ROOT, library_summaries
from backend.part_library_models import CATEGORY_KINDS, RATING_UNITS, REQUIRED_RATINGS, TEST_KINDS

UNCONFIRMED = "unconfirmed: replace with 'datasheet p.N' after checking the datasheet"
TEST_FIELDS = {"diode_forward_voltage": ["current"], "zener_voltage": ["current"],
               "mosfet_threshold": ["drain_current"],
               "mosfet_on_resistance": ["gate_voltage", "drain_current"],
               "bjt_current_gain": ["collector_voltage", "collector_current"],
               "bjt_saturation_voltage": ["collector_current", "base_current"]}


def list_parts() -> int:
    """Print every part with its trust level, so drafts are never mistaken for verified."""
    for part in sorted(LIBRARY.values(), key=lambda part: (part.category, part.name)):
        print(f"{part.trust.level:8}  {part.category:9} {part.id:14} {part.name}  ({part.package})")
    print(f"\n{len(LIBRARY)} part(s); "
          f"{sum(part.trust.level == 'verified' for part in LIBRARY.values())} verified.")
    return 0


def format_result(result: CharacterizationResult) -> str:
    """One readable line per test: what was measured against what was stated."""
    bounds = f"[{'' if result.min is None else f'{result.min:g}'}, " \
             f"{'' if result.max is None else f'{result.max:g}'}]"
    value = "—" if result.measured is None else f"{result.measured:.4g}"
    verdict = "PASS" if result.passed else "FAIL"
    return f"  {verdict}  {result.test:24} {value:>10} {result.unit:4} {bounds:16} {result.detail}"


def verify_parts(part_ids: list[str]) -> int:
    """Run characterization tests on real ngspice; exit nonzero if any test fails."""
    unknown = [part_id for part_id in part_ids if part_id not in LIBRARY]
    if unknown:
        print(f"Unknown part(s): {', '.join(unknown)}", file=sys.stderr)
        return 2
    selected = [LIBRARY[part_id] for part_id in part_ids] or sorted(
        LIBRARY.values(), key=lambda part: part.id)
    failures = 0
    for part in selected:
        print(f"{part.id} ({part.name}, {part.trust.level})")
        results = characterize(part)
        failures += sum(not result.passed for result in results)
        print("\n".join(format_result(result) for result in results))
    print(f"\n{failures} failing test(s) across {len(selected)} part(s).")
    return 1 if failures else 0


def scaffold(category: str, part_id: str, kind: str) -> dict[str, object]:
    """A draft part file with every required field present and clearly unconfirmed."""
    test = next(name for name, kinds in TEST_KINDS.items() if kind in kinds)
    return {"id": part_id, "name": part_id.upper(), "kind": kind, "category": category,
            "description": "TODO: one-line description", "package": "TODO",
            "datasheet": {"manufacturer": None, "url": None},
            "model": {"parameters": {"IS": 1e-14}},
            "ratings": {name: {"value": 1, "unit": RATING_UNITS[name], "source": UNCONFIRMED}
                        for name in sorted(REQUIRED_RATINGS[category])},
            "characterization": [{"test": test, **dict.fromkeys(TEST_FIELDS[test]),
                                  "min": None, "max": None, "source": UNCONFIRMED}],
            "trust": {"level": "draft", "reviewed_by": None, "reviewed_on": None, "notes": ""}}


def new_part(target: str, kind: str) -> int:
    """Create part.draft.json, which the loader ignores until it is complete and renamed."""
    category, _, part_id = target.partition("/")
    if category not in CATEGORY_KINDS or kind not in CATEGORY_KINDS[category] or not part_id:
        print(f"Use <category>/<id> with a kind valid for it: "
              f"{ {name: sorted(kinds) for name, kinds in CATEGORY_KINDS.items()} }", file=sys.stderr)
        return 2
    folder: Path = PARTS_ROOT / category / part_id
    if folder.exists():
        print(f"{folder} already exists; not overwriting it.", file=sys.stderr)
        return 2
    folder.mkdir(parents=True)
    path = folder / "part.draft.json"
    path.write_text(json.dumps(scaffold(category, part_id, kind), indent=2) + "\n")
    print(f"Created {path}.\nFill in the model, ratings and test values, rename it to part.json, "
          f"then run: python -m backend.parts_cli verify {part_id} && python -m backend.parts_cli index")
    return 0


def index_text() -> str:
    """The browser's copy of the library: summaries only, in a stable order."""
    return json.dumps(library_summaries(), indent=1, sort_keys=True) + "\n"


def write_index() -> int:
    """Regenerate circuits/parts-index.json after adding or changing a part."""
    INDEX_PATH.write_text(index_text())
    print(f"Wrote {len(LIBRARY)} part(s) to {INDEX_PATH}")
    return 0


def main(arguments: list[str] | None = None) -> int:
    """Dispatch one subcommand."""
    parser = argparse.ArgumentParser(prog="python -m backend.parts_cli")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="list parts and their trust level")
    verify = commands.add_parser("verify", help="run characterization tests on ngspice")
    verify.add_argument("parts", nargs="*", help="part ids (default: all)")
    create = commands.add_parser("new", help="scaffold a draft part file")
    create.add_argument("target", help="<category>/<id>, e.g. mosfet/irlz44n")
    create.add_argument("--kind", required=True, help="D, NMOS, PMOS, NPN or PNP")
    commands.add_parser("index", help="regenerate the browser parts index")
    options = parser.parse_args(arguments)
    if options.command == "list":
        return list_parts()
    if options.command == "index":
        return write_index()
    if options.command == "verify":
        return verify_parts(options.parts)
    return new_part(options.target, options.kind)


if __name__ == "__main__":
    sys.exit(main())
